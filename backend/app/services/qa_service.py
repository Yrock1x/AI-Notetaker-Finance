"""Deal-scoped RAG Q&A over SQLite + sqlite-vec embeddings."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from app.db.models import Document, Meeting, TranscriptSegment
from app.llm.chunking import _estimate_tokens
from app.llm.guardrails import FinancialGuardrails
from app.llm.prompts.qa import RAG_QA
from app.llm.router import TASK_QA_MEETING, TASK_QA_RAG, LLMRouter

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

    # Deal-scoped Q&A budget: if the deal's ENTIRE corpus (all meeting
    # transcripts + extracted document text) fits within this many estimated
    # tokens, answer it by feeding the whole corpus to a cheap model — full
    # recall, no chunk-boundary / stale-embedding / top-k misses. Above it, fall
    # back to RAG. Same sizing rationale as MEETING_FULL_MAX_TOKENS.
    DEAL_FULL_MAX_TOKENS = int(os.getenv("QA_DEAL_FULL_MAX_TOKENS", "24000"))

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
        meeting_ids: list[UUID] | None = None,
    ) -> QAResponse:
        """Answer a question scoped to a whole deal, or to a subset of its
        meetings when ``meeting_ids`` is given (None/[] = the whole deal).

        Context-first: if the (possibly narrowed) corpus fits the budget, feed
        it directly to a cheap model — full recall, no retrieval misses.
        Otherwise fall back to RAG (narrowed to the same meetings).
        """
        blocks = self._fetch_deal_corpus(deal_id, meeting_ids=meeting_ids)
        total_tokens = sum(b["tokens"] for b in blocks)

        if blocks and total_tokens <= self.DEAL_FULL_MAX_TOKENS:
            # One source "chunk" per meeting / document so the shared synthesis
            # path (prompt, citation parsing, grounding) is fully reused and the
            # model can cite which meeting/document a fact came from.
            search_results = [
                {
                    "id": f"chunk_{i}",
                    "source_type": b["source_type"],
                    "source_id": b["source_id"],
                    "text": f"## {b['label']}\n{b['text']}",
                    "similarity": 1.0,
                    "metadata": (
                        {"meeting_id": b["source_id"]}
                        if b["source_type"] == "transcript_segment"
                        else {}
                    ),
                }
                for i, b in enumerate(blocks)
            ]
            logger.info(
                "qa_deal_full_context",
                deal_id=str(deal_id),
                sources=len(blocks),
                corpus_tokens=total_tokens,
            )
            return await self._synthesize(
                deal_id, question, search_results, TASK_QA_MEETING
            )

        logger.info(
            "qa_deal_rag_fallback",
            deal_id=str(deal_id),
            corpus_tokens=total_tokens,
            reason="empty" if not blocks else "too_large",
        )
        return await self._ask_rag(
            deal_id, question, top_k=top_k, meeting_ids=meeting_ids
        )

    async def _ask_rag(
        self,
        deal_id: UUID,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        meeting_ids: list[UUID] | None = None,
    ) -> QAResponse:
        """Deal-scoped RAG: embed the question, KNN over the deal's embeddings,
        synthesize. Used when the full corpus is too large to fit in context.

        When ``meeting_ids`` is given, the KNN is restricted to those meetings'
        transcript-segment embeddings. Transcript embeddings store
        ``source_id = TranscriptSegment.id`` (not the meeting id), so resolve the
        meetings to their segment ids and pass that as the matcher allowlist.
        """
        from app.db.vectors import match_embeddings_for_deal

        source_ids: list[str] | None = None
        if meeting_ids:
            # Only finalized segments have embeddings (live partials are not
            # embedded — see internal/transcription.embed_meeting). Mirror the
            # is_partial=False filter from _fetch_meeting_transcript so a
            # still-being-transcribed meeting (partials only) short-circuits to
            # the "no transcript" answer instead of an empty KNN.
            source_ids = [
                str(row[0])
                for row in self.session.query(TranscriptSegment.id)
                .filter(
                    TranscriptSegment.meeting_id.in_([str(m) for m in meeting_ids]),
                    TranscriptSegment.is_partial.is_(False),
                )
                .all()
            ]
            if not source_ids:
                # The selected meetings have no transcript segments to search —
                # short-circuit before spending an embedding call.
                return QAResponse(
                    answer=(
                        "I could not find any transcript text for the selected "
                        "meeting(s) to answer this question."
                    ),
                    citations=[],
                    confidence="low",
                    source_coverage="No transcript available for the selected meetings.",
                )

        query_vector = await self.llm_router.embed(question)

        rows = match_embeddings_for_deal(
            self.session,
            deal_id=str(deal_id),
            query_vector=query_vector,
            top_k=top_k,
            min_similarity=self.MIN_SIMILARITY,
            source_ids=source_ids,
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
            # A meeting too big to fit context falls back to RAG scoped to that
            # one meeting's transcript segments (not the whole deal — the user
            # asked about this meeting specifically).
            return await self._ask_rag(
                deal_id=deal_id, question=question, meeting_ids=[meeting_id]
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

    def _fetch_deal_corpus(
        self, deal_id: UUID, meeting_ids: list[UUID] | None = None
    ) -> list[dict]:
        """The deal's Q&A corpus as per-source blocks: every meeting's finalized
        transcript plus every document's extracted text. Blank/unprocessed
        sources are skipped. Each block carries an `_estimate_tokens` count so the
        caller can decide whether the corpus fits in context.

        When ``meeting_ids`` is given the corpus is narrowed to those meetings'
        transcripts and the deal-wide documents are skipped — a meeting-subset
        scope is about what was said in those calls, not the whole data room.
        """
        blocks: list[dict] = []

        meetings_q = self.session.query(
            Meeting.id, Meeting.title, Meeting.meeting_date, Meeting.created_at
        ).filter(Meeting.deal_id == str(deal_id))
        if meeting_ids:
            meetings_q = meetings_q.filter(
                Meeting.id.in_([str(m) for m in meeting_ids])
            )
        meetings = meetings_q.order_by(
            Meeting.meeting_date, Meeting.created_at
        ).all()
        for m in meetings:
            text = self._fetch_meeting_transcript(m[0])
            if not text.strip():
                continue
            when = m[2] or m[3]
            label = f"Meeting: {m[1] or 'Untitled'}"
            if when:
                label += f" ({when})"
            blocks.append(
                {
                    "source_type": "transcript_segment",
                    "source_id": str(m[0]),
                    "label": label,
                    "text": text,
                    "tokens": _estimate_tokens(text),
                }
            )

        # Deal-wide documents only when not narrowed to a meeting subset.
        docs = (
            []
            if meeting_ids
            else self.session.query(
                Document.id, Document.title, Document.extracted_text
            )
            .filter(Document.deal_id == str(deal_id))
            .all()
        )
        for d in docs:
            text = (d[2] or "").strip()
            if not text:
                continue
            blocks.append(
                {
                    "source_type": "document_chunk",
                    "source_id": str(d[0]),
                    "label": f"Document: {d[1] or 'Untitled'}",
                    "text": text,
                    "tokens": _estimate_tokens(text),
                }
            )

        return blocks

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
