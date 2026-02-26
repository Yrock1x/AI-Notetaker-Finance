import json
from uuid import UUID
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.llm.router import LLMRouter
from app.llm.prompts.base import BasePromptTemplate
from app.models.analysis import Analysis
from app.services.transcript_service import TranscriptService

logger = structlog.get_logger(__name__)

# Map call types to prompt template modules and attribute names
CALL_TYPE_PROMPTS: dict[str, tuple[str, str]] = {
    "diligence": ("app.llm.prompts.diligence", "DILIGENCE_CALL_ANALYSIS"),
    "management_presentation": ("app.llm.prompts.management_presentation", "MANAGEMENT_PRESENTATION_ANALYSIS"),
    "buyer_call": ("app.llm.prompts.buyer_call", "BUYER_CALL_ANALYSIS"),
    "financial_review": ("app.llm.prompts.financial_review", "FINANCIAL_REVIEW_ANALYSIS"),
    "qoe": ("app.llm.prompts.qoe", "QOE_ANALYSIS"),
    "summarization": ("app.llm.prompts.summarization", "SUMMARIZATION"),
}


def _load_prompt(call_type: str) -> BasePromptTemplate:
    """Dynamically load a prompt template by call type."""
    import importlib

    entry = CALL_TYPE_PROMPTS.get(call_type)
    if not entry:
        raise ValueError(f"Unknown call type: {call_type}")

    module_path, attr_name = entry
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


class AnalysisService:
    def __init__(
        self,
        db: AsyncSession,
        llm_router: LLMRouter,
        transcript_service: Optional[TranscriptService] = None,
    ) -> None:
        self.db = db
        self.llm_router = llm_router
        self.transcript_service = transcript_service or TranscriptService(db)

    async def run_analysis(
        self,
        meeting_id: UUID,
        org_id: UUID,
        call_type: str,
        requested_by: Optional[UUID] = None,
    ) -> Analysis:
        """Run an AI analysis on a meeting transcript.

        1. Fetch the transcript with speaker-attributed text
        2. Load the appropriate prompt for the call type
        3. Send to LLM via the router
        4. Parse structured output
        5. Store the analysis record
        """
        version = await self._next_version(meeting_id, call_type)

        analysis = Analysis(
            meeting_id=meeting_id,
            org_id=org_id,
            call_type=call_type,
            model_used="",
            prompt_version="v1",
            status="running",
            requested_by=requested_by,
            version=version,
        )
        self.db.add(analysis)
        await self.db.flush()

        try:
            # Get transcript with speaker attribution
            transcript = await self.transcript_service.get_transcript(meeting_id)
            transcript_text = await self.transcript_service.get_full_text_with_speakers(
                transcript.id
            )

            # Load and render the prompt template
            prompt_template = _load_prompt(call_type)
            system_prompt, user_prompt = prompt_template.render(
                transcript=transcript_text
            )

            # Call the LLM
            response = await self.llm_router.complete(
                task_type="analysis",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=8192,
                temperature=0.0,
            )

            # Parse the structured JSON output
            structured_output = self._parse_llm_output(response.content)

            # Update analysis record
            analysis.structured_output = structured_output
            analysis.model_used = response.model
            analysis.prompt_version = prompt_template.version
            analysis.status = "completed"
            await self.db.flush()

            logger.info(
                "analysis_completed",
                analysis_id=str(analysis.id),
                meeting_id=str(meeting_id),
                call_type=call_type,
                model=response.model,
            )

        except Exception as e:
            analysis.status = "failed"
            analysis.error_message = str(e)
            await self.db.flush()

            logger.error(
                "analysis_failed",
                analysis_id=str(analysis.id),
                meeting_id=str(meeting_id),
                call_type=call_type,
                error=str(e),
            )
            raise

        return analysis

    async def rerun_analysis(self, analysis_id: UUID) -> Analysis:
        """Re-run an existing analysis with the latest model/prompt version."""
        original = await self.get_analysis(analysis_id)
        return await self.run_analysis(
            meeting_id=original.meeting_id,
            org_id=original.org_id,
            call_type=original.call_type,
            requested_by=original.requested_by,
        )

    async def get_analysis(self, analysis_id: UUID) -> Analysis:
        """Get an analysis by ID."""
        stmt = select(Analysis).where(Analysis.id == analysis_id)
        result = await self.db.execute(stmt)
        analysis = result.scalar_one_or_none()
        if analysis is None:
            raise NotFoundError("Analysis", str(analysis_id))
        return analysis

    async def get_latest_analysis(
        self, meeting_id: UUID, call_type: str
    ) -> Optional[Analysis]:
        """Get the most recent completed analysis of a given type for a meeting."""
        stmt = (
            select(Analysis)
            .where(
                Analysis.meeting_id == meeting_id,
                Analysis.call_type == call_type,
                Analysis.status == "completed",
            )
            .order_by(Analysis.version.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_analyses(self, meeting_id: UUID) -> list[Analysis]:
        """List all analyses for a meeting, most recent first."""
        stmt = (
            select(Analysis)
            .where(Analysis.meeting_id == meeting_id)
            .order_by(Analysis.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _next_version(self, meeting_id: UUID, call_type: str) -> int:
        """Get the next version number for a given meeting + call type."""
        stmt = select(func.coalesce(func.max(Analysis.version), 0)).where(
            Analysis.meeting_id == meeting_id,
            Analysis.call_type == call_type,
        )
        result = await self.db.execute(stmt)
        current_max = result.scalar_one()
        return current_max + 1

    @staticmethod
    def _parse_llm_output(content: str) -> dict:
        """Parse LLM response into structured JSON.

        Handles both raw JSON and markdown-fenced JSON blocks.
        """
        text = content.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_output": content, "parse_error": True}
