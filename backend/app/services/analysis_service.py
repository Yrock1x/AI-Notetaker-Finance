"""LLM-driven meeting analyses on the SQLite layer.

Fetches the meeting's transcript segments, renders a call-type-specific
prompt, calls the task-routed LLM, parses the structured JSON output, and
writes an ``analyses`` row. Versioning works the same as before — each
(meeting_id, call_type) tuple is independently versioned.

DB work is synchronous SQLAlchemy on the request-scoped ``Session``. The
methods stay ``async`` so callers can keep awaiting them (and so the LLM
call inside can be awaited); the session calls inside are plain sync calls.
The service never commits — the ``get_db`` dependency commits on success
(and the internal pipeline caller commits its own session). We ``flush`` so
generated ids / column defaults are populated.
"""

from __future__ import annotations

import json
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Analysis, Deal, Meeting, TranscriptSegment
from app.llm.prompts.base import BasePromptTemplate
from app.llm.router import (
    TASK_IC_MEMO,
    TASK_SUMMARIZATION,
    LLMRouter,
)

logger = structlog.get_logger(__name__)


CALL_TYPE_PROMPTS: dict[str, tuple[str, str]] = {
    "diligence": ("app.llm.prompts.diligence", "DILIGENCE_CALL_ANALYSIS"),
    "management_presentation": (
        "app.llm.prompts.management_presentation",
        "MANAGEMENT_PRESENTATION_ANALYSIS",
    ),
    "buyer_call": ("app.llm.prompts.buyer_call", "BUYER_CALL_ANALYSIS"),
    "financial_review": (
        "app.llm.prompts.financial_review",
        "FINANCIAL_REVIEW_ANALYSIS",
    ),
    "qoe": ("app.llm.prompts.qoe", "QOE_ANALYSIS"),
    "summarization": (
        "app.llm.prompts.summarization",
        "MEETING_SUMMARIZATION",
    ),
}

# Routing hint — most analyses are heavy reasoning; summarization is cheap.
_CALL_TYPE_TASK: dict[str, str] = {
    "summarization": TASK_SUMMARIZATION,
}


def _load_prompt(call_type: str) -> BasePromptTemplate:
    import importlib

    entry = CALL_TYPE_PROMPTS.get(call_type)
    if not entry:
        raise ValueError(f"Unknown call type: {call_type}")
    module_path, attr_name = entry
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


class AnalysisService:
    """Runs + persists analyses against the SQLite-backed schema."""

    def __init__(self, session: Session, llm_router: LLMRouter) -> None:
        self.session = session
        self.llm_router = llm_router

    # ------------------------------------------------------------------ run

    async def run_analysis(
        self,
        meeting_id: UUID,
        org_id: UUID,
        call_type: str,
        requested_by: UUID | None = None,
    ) -> dict:
        version = await self._next_version(meeting_id, call_type)

        analysis = Analysis(
            meeting_id=str(meeting_id),
            org_id=str(org_id),
            call_type=call_type,
            model_used="",
            prompt_version="v1",
            status="running",
            version=version,
            requested_by=str(requested_by) if requested_by else None,
        )
        self.session.add(analysis)
        self.session.flush()  # populate id / created_at / updated_at defaults
        analysis_id = analysis.id

        try:
            transcript_text = await self._fetch_transcript_text(meeting_id)
            prompt_template = _load_prompt(call_type)
            render_kwargs: dict[str, str] = {"transcript": transcript_text}

            if call_type == "summarization":
                meeting = self._fetch_meeting_with_deal(meeting_id)
                render_kwargs["deal_name"] = (
                    (meeting or {}).get("deal_name") or "Unknown"
                )
                render_kwargs["meeting_type"] = call_type

            system_prompt, user_prompt = prompt_template.render(**render_kwargs)

            response = await self.llm_router.complete(
                task_type=_CALL_TYPE_TASK.get(call_type, TASK_IC_MEMO),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                # Fireworks rejects max_tokens > 4096 without stream=true.
                # 4096 is plenty for an IC memo / summary — the JSON schemas
                # we render are well under that budget.
                max_tokens=4096,
                temperature=0.0,
            )

            structured_output = self._parse_llm_output(response.content)
            status_ = (
                "partial"
                if isinstance(structured_output, dict)
                and structured_output.get("parse_error")
                else "completed"
            )

            analysis.structured_output = structured_output
            analysis.model_used = response.model
            analysis.prompt_version = prompt_template.version
            analysis.status = status_
            self.session.flush()

            logger.info(
                "analysis_completed",
                analysis_id=analysis_id,
                meeting_id=str(meeting_id),
                call_type=call_type,
                model=response.model,
            )
            return self._to_dict(analysis)

        except Exception as exc:
            analysis.status = "failed"
            analysis.error_message = str(exc)
            # Commit (not just flush) so the failed status survives — the
            # request's get_db dependency rolls the transaction back on the
            # re-raise below, which would otherwise discard this write and leave
            # the row stuck in "running".
            self.session.commit()
            logger.error(
                "analysis_failed",
                analysis_id=analysis_id,
                meeting_id=str(meeting_id),
                call_type=call_type,
                error=str(exc),
            )
            raise

    # -------------------------------------------------------- rerun + reads

    async def rerun_analysis(self, analysis_id: UUID) -> dict:
        original = await self.get_analysis(analysis_id)
        return await self.run_analysis(
            meeting_id=UUID(original["meeting_id"]),
            org_id=UUID(original["org_id"]),
            call_type=original["call_type"],
            requested_by=(
                UUID(original["requested_by"]) if original.get("requested_by") else None
            ),
        )

    async def get_analysis(self, analysis_id: UUID) -> dict:
        analysis = self.session.scalar(
            select(Analysis).where(Analysis.id == str(analysis_id))
        )
        if analysis is None:
            raise LookupError(f"analysis {analysis_id} not found")
        return self._to_dict(analysis)

    async def list_analyses(self, meeting_id: UUID) -> list[dict]:
        rows = self.session.scalars(
            select(Analysis)
            .where(Analysis.meeting_id == str(meeting_id))
            .order_by(Analysis.created_at.desc())
        ).all()
        return [self._to_dict(a) for a in rows]

    # --------------------------------------------------------------- helpers

    async def _next_version(self, meeting_id: UUID, call_type: str) -> int:
        latest = self.session.scalar(
            select(Analysis.version)
            .where(
                Analysis.meeting_id == str(meeting_id),
                Analysis.call_type == call_type,
            )
            .order_by(Analysis.version.desc())
            .limit(1)
        )
        return (latest + 1) if latest is not None else 1

    async def _fetch_transcript_text(self, meeting_id: UUID) -> str:
        """Finalized transcript segments, sorted, as speaker-attributed text."""
        segments = self.session.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.meeting_id == str(meeting_id),
                TranscriptSegment.is_partial == False,  # noqa: E712
            )
            .order_by(TranscriptSegment.start_time)
        ).all()
        lines: list[str] = []
        for seg in segments:
            label = seg.speaker_name or seg.speaker_label or "Speaker"
            lines.append(f"{label}: {(seg.text or '').strip()}")
        return "\n".join(lines)

    def _fetch_meeting_with_deal(self, meeting_id: UUID) -> dict | None:
        meeting = self.session.scalar(
            select(Meeting).where(Meeting.id == str(meeting_id))
        )
        if meeting is None:
            return None
        deal_name = "Unknown"
        if meeting.deal_id:
            deal_name = (
                self.session.scalar(
                    select(Deal.name).where(Deal.id == meeting.deal_id)
                )
                or "Unknown"
            )
        return {
            "id": meeting.id,
            "deal_id": meeting.deal_id,
            "title": meeting.title,
            "deal_name": deal_name,
        }

    @staticmethod
    def _to_dict(analysis: Analysis) -> dict:
        return {
            "id": analysis.id,
            "meeting_id": analysis.meeting_id,
            "org_id": analysis.org_id,
            "call_type": analysis.call_type,
            "structured_output": analysis.structured_output,
            "model_used": analysis.model_used,
            "prompt_version": analysis.prompt_version,
            "grounding_score": analysis.grounding_score,
            "status": analysis.status,
            "error_message": analysis.error_message,
            "requested_by": analysis.requested_by,
            "version": analysis.version,
            "created_at": analysis.created_at,
            "updated_at": analysis.updated_at,
        }

    @staticmethod
    def _parse_llm_output(content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_output": content, "parse_error": True}
