import asyncio
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.llm.claude_provider import ClaudeProvider
from app.llm.router import LLMRouter
from app.services.analysis_service import AnalysisService
from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(base=BaseTask, bind=True, queue="analysis")
def run_analysis(self, meeting_id: str, call_type: str | None = None, requested_by: str | None = None) -> str:
    """Run LLM analysis on meeting transcript with specified call type."""

    async def _analyze():
        settings = get_settings()

        async with async_session_factory() as session:
            try:
                # Get the meeting to find its org_id
                from app.services.meeting_service import MeetingService
                from app.integrations.aws.s3 import get_s3_client

                s3_client = get_s3_client()
                meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
                meeting = await meeting_svc.get_meeting(UUID(meeting_id))

                # Create an LLM router with Claude provider
                llm_router = LLMRouter()
                claude_provider = ClaudeProvider(api_key=settings.anthropic_api_key)
                llm_router.register_provider("claude", claude_provider)

                # Create the analysis service
                analysis_svc = AnalysisService(db=session, llm_router=llm_router)

                # Default to 'summarization' if no call_type specified
                effective_call_type = call_type or "summarization"

                # Run the analysis
                requested_by_uuid = UUID(requested_by) if requested_by else None
                analysis = await analysis_svc.run_analysis(
                    meeting_id=UUID(meeting_id),
                    org_id=meeting.org_id,
                    call_type=effective_call_type,
                    requested_by=requested_by_uuid,
                )

                await session.commit()

                logger.info(
                    "run_analysis_complete",
                    meeting_id=meeting_id,
                    analysis_id=str(analysis.id),
                    call_type=effective_call_type,
                )
                return str(analysis.id)
            except Exception:
                await session.rollback()
                raise

    return _run_async(_analyze())


@celery_app.task(base=BaseTask, bind=True, queue="analysis")
def rerun_analysis(self, analysis_id: str, requested_by: str) -> str:
    """Re-run an existing analysis, creating a new version."""

    async def _rerun():
        settings = get_settings()

        async with async_session_factory() as session:
            try:
                # Create an LLM router with Claude provider
                llm_router = LLMRouter()
                claude_provider = ClaudeProvider(api_key=settings.anthropic_api_key)
                llm_router.register_provider("claude", claude_provider)

                # Create the analysis service and get the original analysis
                analysis_svc = AnalysisService(db=session, llm_router=llm_router)
                original = await analysis_svc.get_analysis(UUID(analysis_id))

                # Re-run with the original call_type
                new_analysis = await analysis_svc.run_analysis(
                    meeting_id=original.meeting_id,
                    org_id=original.org_id,
                    call_type=original.call_type,
                    requested_by=UUID(requested_by),
                )

                await session.commit()

                logger.info(
                    "rerun_analysis_complete",
                    original_analysis_id=analysis_id,
                    new_analysis_id=str(new_analysis.id),
                    call_type=original.call_type,
                )
                return str(new_analysis.id)
            except Exception:
                await session.rollback()
                raise

    return _run_async(_rerun())
