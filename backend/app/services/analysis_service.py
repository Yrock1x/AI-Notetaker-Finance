"""LLM-driven meeting analyses on Supabase.

Fetches the meeting's transcript segments, renders a call-type-specific
prompt, calls the task-routed LLM, parses the structured JSON output, and
writes an ``analyses`` row. Versioning works the same as before — each
(meeting_id, call_type) tuple is independently versioned.
"""

from __future__ import annotations

import json
from uuid import UUID

import structlog
from supabase import Client

from app.llm.prompts.base import BasePromptTemplate
from app.llm.router import (
    LLMRouter,
    TASK_IC_MEMO,
    TASK_SUMMARIZATION,
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
    """Runs + persists analyses against the Supabase-backed schema."""

    def __init__(self, supabase: Client, llm_router: LLMRouter) -> None:
        self.supabase = supabase
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

        insert_row = {
            "meeting_id": str(meeting_id),
            "org_id": str(org_id),
            "call_type": call_type,
            "model_used": "",
            "prompt_version": "v1",
            "status": "running",
            "version": version,
            "requested_by": str(requested_by) if requested_by else None,
        }
        analysis = (
            self.supabase.table("analyses")
            .insert(insert_row)
            .execute()
            .data[0]
        )
        analysis_id = analysis["id"]

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
                max_tokens=8192,
                temperature=0.0,
            )

            structured_output = self._parse_llm_output(response.content)
            status_ = (
                "partial"
                if isinstance(structured_output, dict) and structured_output.get("parse_error")
                else "completed"
            )

            (
                self.supabase.table("analyses")
                .update(
                    {
                        "structured_output": structured_output,
                        "model_used": response.model,
                        "prompt_version": prompt_template.version,
                        "status": status_,
                    }
                )
                .eq("id", analysis_id)
                .execute()
            )

            logger.info(
                "analysis_completed",
                analysis_id=analysis_id,
                meeting_id=str(meeting_id),
                call_type=call_type,
                model=response.model,
            )
            return {**analysis, "structured_output": structured_output, "status": status_}

        except Exception as exc:
            (
                self.supabase.table("analyses")
                .update({"status": "failed", "error_message": str(exc)})
                .eq("id", analysis_id)
                .execute()
            )
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
        rows = (
            self.supabase.table("analyses")
            .select("*")
            .eq("id", str(analysis_id))
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            raise LookupError(f"analysis {analysis_id} not found")
        return rows[0]

    async def list_analyses(self, meeting_id: UUID) -> list[dict]:
        return (
            self.supabase.table("analyses")
            .select("*")
            .eq("meeting_id", str(meeting_id))
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

    # --------------------------------------------------------------- helpers

    async def _next_version(self, meeting_id: UUID, call_type: str) -> int:
        rows = (
            self.supabase.table("analyses")
            .select("version")
            .eq("meeting_id", str(meeting_id))
            .eq("call_type", call_type)
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return (rows[0]["version"] + 1) if rows else 1

    async def _fetch_transcript_text(self, meeting_id: UUID) -> str:
        """Finalized transcript segments, sorted, as speaker-attributed text."""
        segments = (
            self.supabase.table("transcript_segments")
            .select("speaker_label, speaker_name, text, start_time")
            .eq("meeting_id", str(meeting_id))
            .eq("is_partial", False)
            .order("start_time")
            .execute()
            .data
            or []
        )
        lines: list[str] = []
        for seg in segments:
            label = seg.get("speaker_name") or seg.get("speaker_label") or "Speaker"
            lines.append(f"{label}: {seg.get('text','').strip()}")
        return "\n".join(lines)

    def _fetch_meeting_with_deal(self, meeting_id: UUID) -> dict | None:
        meeting_rows = (
            self.supabase.table("meetings")
            .select("id, deal_id, title")
            .eq("id", str(meeting_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        if not meeting_rows:
            return None
        meeting = meeting_rows[0]
        deal_rows = (
            self.supabase.table("deals")
            .select("name")
            .eq("id", meeting["deal_id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        return {
            **meeting,
            "deal_name": (deal_rows[0]["name"] if deal_rows else "Unknown"),
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
