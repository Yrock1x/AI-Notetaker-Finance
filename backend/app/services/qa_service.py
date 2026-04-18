"""Deal-scoped RAG Q&A over Supabase-hosted embeddings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from supabase import Client

from app.llm.guardrails import FinancialGuardrails
from app.llm.prompts.qa import RAG_QA
from app.llm.router import LLMRouter, TASK_QA_RAG

logger = structlog.get_logger(__name__)


@dataclass
class Citation:
    chunk_id: str
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
       2. ``supabase.rpc('match_embeddings_for_deal', ...)`` returns top-k
          chunks filtered by ``deal_id`` (RLS makes sure the caller has
          access to that deal).
       3. Render the RAG prompt, call the task-routed LLM.
       4. Parse citations, run grounding guardrails, return.
    """

    DEFAULT_TOP_K = 15
    MIN_SIMILARITY = 0.3

    def __init__(
        self,
        supabase: Client,
        llm_router: LLMRouter,
    ) -> None:
        self.supabase = supabase
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

        rpc = self.supabase.rpc(
            "match_embeddings_for_deal",
            {
                "p_deal_id": str(deal_id),
                "p_query": query_vector,
                "p_top_k": top_k,
                "p_min_similarity": self.MIN_SIMILARITY,
            },
        ).execute()

        search_results = [
            {
                "id": row["id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "text": row["chunk_text"],
                "similarity": row["similarity"],
                "metadata": row.get("metadata") or {},
            }
            for row in (rpc.data or [])
        ]

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

        context = self._format_context(search_results)
        system_prompt, user_prompt = RAG_QA.render(
            question=question, context=context
        )

        response = await self.llm_router.complete(
            task_type=TASK_QA_RAG,
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
                        source_type=r["source_type"],
                        text=r["text"][:200],
                        relevance=cit.get("relevance", "direct"),
                        metadata=r.get("metadata") or {},
                    )
                )
        return out
