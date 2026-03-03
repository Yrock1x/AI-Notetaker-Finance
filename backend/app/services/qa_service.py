import json
import re
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.guardrails import FinancialGuardrails
from app.llm.prompts.qa import RAG_QA
from app.llm.router import LLMRouter
from app.services.embedding_service import EmbeddingService

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
    """Response from the Q&A service including answer text and citations."""

    answer: str
    citations: list[Citation]
    confidence: str  # high, medium, low
    source_coverage: str
    grounding_score: float | None = None
    grounding_status: str = "pending"  # "checked", "skipped", "pending"


class QAService:
    """Deal-scoped RAG Q&A service.

    Pipeline:
    1. Embed the user's question via OpenAI
    2. Vector search in embeddings table filtered by deal_id + org_id
    3. Retrieve top-k chunks with source metadata
    4. Assemble context window with citations
    5. Send to Claude with strict grounding instructions
    6. Parse response, extract citations, validate against sources
    7. Calculate grounding score — reject if below threshold
    """

    DEFAULT_TOP_K = 15

    def __init__(
        self,
        db: AsyncSession,
        llm_router: LLMRouter,
        embedding_service: EmbeddingService,
    ) -> None:
        self.db = db
        self.llm_router = llm_router
        self.embedding_service = embedding_service
        self.guardrails = FinancialGuardrails()

    async def ask(
        self,
        deal_id: UUID,
        org_id: UUID,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        meeting_id: UUID | None = None,
    ) -> QAResponse:
        """Answer a question about a deal with citations from relevant sources."""

        # Step 1-2: Vector search for relevant chunks
        search_results = await self.embedding_service.search(
            query_text=question,
            deal_id=deal_id,
            org_id=org_id,
            top_k=top_k,
            score_threshold=0.3,
        )

        if not search_results:
            return QAResponse(
                answer="I could not find any relevant information in the deal's "
                       "source material to answer this question.",
                citations=[],
                confidence="low",
                source_coverage="No relevant sources found for this question.",
            )

        # Step 3: Format context with chunk IDs for citation
        context = self._format_context(search_results)

        # Step 4-5: Send to LLM with RAG prompt
        system_prompt, user_prompt = RAG_QA.render(
            question=question,
            context=context,
        )

        response = await self.llm_router.complete(
            task_type="qa",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
        )

        # Step 6: Parse the response
        parsed = self._parse_response(response.content)
        answer_text = parsed.get("answer", response.content)
        raw_citations = parsed.get("citations_used", [])
        confidence = parsed.get("confidence", "medium")
        source_coverage = parsed.get("source_coverage", "")

        # Map citations back to source chunks
        citations = self._map_citations(raw_citations, search_results)

        # Step 7: Validate grounding
        grounding_score = None
        grounding_status = "pending"
        try:
            source_chunks = [
                {
                    "text": r["text"],
                    "source_id": r["source_id"],
                    "source_type": r["source_type"],
                }
                for r in search_results
            ]
            citation_dicts = [
                {"text": c.text, "source_id": c.chunk_id}
                for c in citations
            ]
            grounding_result = self.guardrails.check_and_flag(
                answer_text, citation_dicts, source_chunks
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
                    f"\n\n**Note:** Some claims in this answer could not be fully "
                    f"verified against the source material (grounding score: "
                    f"{grounding_score:.2f}). Please verify key facts independently."
                )
        except Exception:
            logger.warning("grounding_check_failed", deal_id=str(deal_id))
            grounding_status = "skipped"
            grounding_score = None

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

    def _format_context(self, search_results: list[dict]) -> str:
        """Format search results into a context string with chunk IDs."""
        sections = []
        for i, result in enumerate(search_results):
            chunk_id = f"chunk_{i}"
            source_type = result["source_type"]
            metadata = result.get("metadata", {})

            header_parts = [f"[CHUNK_ID: {chunk_id}]", f"[Type: {source_type}]"]
            if "speaker_name" in metadata:
                header_parts.append(f"[Speaker: {metadata['speaker_name']}]")
            if "start_time" in metadata:
                header_parts.append(f"[Time: {metadata['start_time']:.1f}s]")
            if "page" in metadata:
                header_parts.append(f"[Page: {metadata['page']}]")

            header = " ".join(header_parts)
            sections.append(f"{header}\n{result['text']}")

        return "\n\n---\n\n".join(sections)

    def _parse_response(self, content: str) -> dict:
        """Parse the LLM response, handling both JSON and plain text."""
        text = content.strip()

        if "```" in text:
            json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
            if json_match:
                text = json_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"answer": content}

    def _map_citations(
        self, raw_citations: list[dict], search_results: list[dict]
    ) -> list[Citation]:
        """Map parsed citation references back to source chunks."""
        citations = []
        chunk_map = {f"chunk_{i}": r for i, r in enumerate(search_results)}

        for cit in raw_citations:
            chunk_id = cit.get("chunk_id", "")
            if chunk_id in chunk_map:
                result = chunk_map[chunk_id]
                citations.append(
                    Citation(
                        chunk_id=chunk_id,
                        source_type=result["source_type"],
                        text=result["text"][:200],
                        relevance=cit.get("relevance", "direct"),
                        metadata=result.get("metadata", {}),
                    )
                )

        return citations
