"""Deal-scoped RAG Q&A over SQLite + sqlite-vec embeddings."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from app.db.models import TranscriptSegment
from app.llm.chunking import _estimate_tokens
from app.llm.guardrails import FinancialGuardrails
from app.llm.prompts.qa import RAG_QA
from app.llm.router import LLMRouter, TASK_QA_MEETING, TASK_QA_RAG

logger = structlog.get_logger(__name__)


@dataclass
class Citation:
    chunk_id: str
    source_id: str
    source_type: str
    text: str
    relevance: str = "direct"
    metadata: dict = field(default_factory=dict)


@dataclass
class QAResponse:
    answer: str
    citations: list[Citation]
    confidence: str
    source_coverage: str
    grounding_score: float | None = None
    grounding_status: str = "pending"


class QAService:
    """RAG pipeline:
       1. Embed the question via the LLM router (Fireworks nomic by default)
       2. ``app.db.vectors.match_embeddings_for_deal`` returns top-k chunks
          filtered by ``deal_id`` (the caller's org access is enforced by the
          endpoint before this runs).
       3. Render the RAG prompt, call the task-routed LLM.
       4. Parse citations, run grounding guardrails, return.
    """

    DEFAULT_TOP_K = 15
    MIN_SIMILARITY = 0.3

    # Single-meeting Q&A budget: if a meeting's full transcript fits within this
    # many estimated tokens, answer it by stuffing the whole transcript into a
    # cheap model (no RAG). Above it, fall back to deal-scoped RAG. Sized to leave
    # headroom for the prompt + answer inside a ~32k context window.
    MEETING_FULL_MAX_TOKENS = int(os.getenv("QA_MEETING_FULL_MAX_TOKENS", "24000"))

    def __init__(
        self,
        session: Session,
        llm_router: LLMRouter,
    ) -> None:
        self.session = session
        self.llm_router = llm_router
        self.guardrails = FinancialGuardrails()

    async def ask(
        self,
        deal_id: UUID,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        meeting_id: UUID | None = None,  # noqa: ARG002 - reserved for future filter
    ) -> QAResponse:
        query_vector = await self.llm_router.embed(question)

        from app.db.vectors import match_embeddings_for_deal

        rows = match_embeddings_for_deal(
            self.session,
            deal_id=str(deal_id),
            query_vector=query_vector,
            top_k=top_k,
            min_similarity=self.MIN_SIMILARITY,
        )

        search_results = [
            {
                "id": row["id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "text": row["chunk_text"],
                "similarity": row["similarity"],
                "metadata": row.get("metadata") or {},
            }
            for row in rows
        ]

        # Enrich transcript_segment citations with meeting_id + start_time so
        # the frontend can build a direct link to the exact moment in the
        # meeting transcript. Batched in one query per question.
        ts_ids = [
            str(r["source_id"])
            for r in search_results
            if r["source_type"] == "transcript_segment"
        ]
        if ts_ids:
            seg_rows = (
                self.session.query(
                    TranscriptSegment.id,
                    TranscriptSegment.meeting_id,
                    TranscriptSegment.start_time,
                )
                .filter(TranscriptSegment.id.in_(ts_ids))
                .all()
            )
            by_id = {str(row[0]): row for row in seg_rows}
            for r in search_results:
                if r["source_type"] != "transcript_segment":
                    continue
                seg = by_id.get(str(r["source_id"]))
                if not seg:
                    continue
                md = dict(r.get("metadata") or {})
                md.setdefault("meeting_id", str(seg[1]))
                md.setdefault("start_time", seg[2])
                r["metadata"] = md

        if not search_results:
            return QAResponse(
                answer=(
                    "I could not find any relevant information in the deal's "
                    "source material to answer this question."
                ),
                citations=[],
                confidence="low",
                source_coverage="No relevant sources found for this question.",
            )

        return await self._synthesize(
            deal_id, question, search_results, TASK_QA_RAG
        )

    async def ask_meeting(
        self,
        deal_id: UUID,
        meeting_id: UUID,
        question: str,
    ) -> QAResponse:
        """Answer a question scoped to a single meeting.

        For one meeting the full transcript is usually small enough to feed
        directly to a cheap model — skipping retrieval avoids stale-embedding
        and chunk-boundary misses entirely. If the transcript is too large (or
        not yet transcribed), fall back to deal-scoped RAG.
        """
        transcript = self._fetch_meeting_transcript(meeting_id)
        tokens = _estimate_tokens(transcript)

        if not transcript.strip() or tokens > self.MEETING_FULL_MAX_TOKENS:
            logger.info(
                "qa_meeting_rag_fallback",
                meeting_id=str(meeting_id),
                transcript_tokens=tokens,
                reason="empty" if not transcript.strip() else "too_large",
            )
            return await self.ask(
                deal_id=deal_id, question=question, meeting_id=meeting_id
            )

        # Present the whole transcript as a single source "chunk" so the shared
        # synthesis path (prompt, citation parsing, grounding) is fully reused.
        search_results = [
            {
                "id": "chunk_0",
                "source_type": "transcript_segment",
                "source_id": str(meeting_id),
                "text": transcript,
                "similarity": 1.0,
                "metadata": {"meeting_id": str(meeting_id)},
            }
        ]
        logger.info(
            "qa_meeting_full_transcript",
            meeting_id=str(meeting_id),
            transcript_tokens=tokens,
        )
        return await self._synthesize(
            deal_id, question, search_results, TASK_QA_MEETING
        )

    async def _synthesize(
        self,
        deal_id: UUID,
        question: str,
        search_results: list[dict],
        task_type: str,
    ) -> QAResponse:
        """Render the RAG prompt over ``search_results``, call the task-routed
        LLM, parse citations, and run grounding guardrails."""
        context = self._format_context(search_results)
        system_prompt, user_prompt = RAG_QA.render(
            question=question, context=context
        )

        response = await self.llm_router.complete(
            task_type=task_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
        )

        parsed = self._parse_response(response.content)
        answer_text = parsed.get("answer", response.content)
        raw_citations = parsed.get("citations_used", [])
        confidence = parsed.get("confidence", "medium")
        source_coverage = parsed.get("source_coverage", "")

        citations = self._map_citations(raw_citations, search_results)

        grounding_score = None
        grounding_status = "pending"
        try:
            source_chunks = [
                {"text": r["text"], "source_id": r["source_id"], "source_type": r["source_type"]}
                for r in search_results
            ]
            grounding_result = self.guardrails.check_and_flag(
                answer_text,
                [{"text": c.text, "source_id": c.chunk_id} for c in citations],
                source_chunks,
            )
            grounding_score = grounding_result.score
            grounding_status = "checked"
            if not grounding_result.is_grounded:
                logger.warning(
                    "qa_low_grounding",
                    deal_id=str(deal_id),
                    score=grounding_score,
                    ungrounded=grounding_result.ungrounded_claims,
                )
                answer_text += (
                    f"\n\n**Note:** Some claims in this answer could not be "
                    f"fully verified against the source material (grounding "
                    f"score: {grounding_score:.2f}). Verify key facts "
                    "independently."
                )
        except Exception:
            logger.warning("grounding_check_failed", deal_id=str(deal_id))
            grounding_status = "skipped"

        logger.info(
            "qa_answered",
            deal_id=str(deal_id),
            citations=len(citations),
            confidence=confidence,
            grounding_score=grounding_score,
        )

        return QAResponse(
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            source_coverage=source_coverage,
            grounding_score=grounding_score,
            grounding_status=grounding_status,
        )

    # ---- helpers -----------------------------------------------------------

    def _fetch_meeting_transcript(self, meeting_id: UUID) -> str:
        """Finalized transcript segments, sorted, as speaker-attributed text."""
        segments = (
            self.session.query(
                TranscriptSegment.speaker_label,
                TranscriptSegment.speaker_name,
                TranscriptSegment.text,
                TranscriptSegment.start_time,
            )
            .filter(
                TranscriptSegment.meeting_id == str(meeting_id),
                TranscriptSegment.is_partial.is_(False),
            )
            .order_by(TranscriptSegment.start_time)
            .all()
        )
        lines: list[str] = []
        for seg in segments:
            label = seg[1] or seg[0] or "Speaker"
            lines.append(f"{label}: {(seg[2] or '').strip()}")
        return "\n".join(lines)

    def _format_context(self, results: list[dict]) -> str:
        sections = []
        for i, result in enumerate(results):
            chunk_id = f"chunk_{i}"
            source_type = result["source_type"]
            metadata = result.get("metadata") or {}
            header_parts = [f"[CHUNK_ID: {chunk_id}]", f"[Type: {source_type}]"]
            if "speaker_name" in metadata:
                header_parts.append(f"[Speaker: {metadata['speaker_name']}]")
            if "start_time" in metadata:
                header_parts.append(f"[Time: {metadata['start_time']:.1f}s]")
            if "page" in metadata:
                header_parts.append(f"[Page: {metadata['page']}]")
            sections.append(f"{' '.join(header_parts)}\n{result['text']}")
        return "\n\n---\n\n".join(sections)

    def _parse_response(self, content: str) -> dict:
        text = content.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
            if m:
                text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"answer": content}

    def _map_citations(
        self, raw: list[dict], results: list[dict]
    ) -> list[Citation]:
        chunk_map = {f"chunk_{i}": r for i, r in enumerate(results)}
        out: list[Citation] = []
        for cit in raw:
            chunk_id = cit.get("chunk_id", "")
            if chunk_id in chunk_map:
                r = chunk_map[chunk_id]
                out.append(
                    Citation(
                        chunk_id=chunk_id,
                        source_id=str(r["source_id"]),
                        source_type=r["source_type"],
                        text=r["text"][:200],
                        relevance=cit.get("relevance", "direct"),
                        metadata=r.get("metadata") or {},
                    )
                )
        return out
