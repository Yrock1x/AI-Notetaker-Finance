from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.gemini_provider import GeminiProvider
from app.llm.router import LLMRouter
from app.services.analysis_service import AnalysisService
from app.tasks.base import BaseTask, get_task_session, run_async
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(base=BaseTask, bind=True, queue="analysis")
def run_analysis(self, meeting_id: str, call_type: str | None = None, requested_by: str | None = None) -> str:
    """Run LLM analysis on meeting transcript with specified call type."""

    async def _analyze():
        settings = get_settings()

        # First, look up the meeting's org_id
        from app.services.meeting_service import MeetingService
        from app.integrations.aws.s3 import get_s3_client

        async with get_task_session() as session:
            s3_client = get_s3_client()
            meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
            meeting = await meeting_svc.get_meeting(UUID(meeting_id))
            org_id = str(meeting.org_id)

        # Now run analysis with RLS scoped to the org
        async with get_task_session(org_id) as session:
            s3_client = get_s3_client()
            meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
            meeting = await meeting_svc.get_meeting(UUID(meeting_id))

            # Create an LLM router with Claude provider
            llm_router = LLMRouter()
            gemini_provider = GeminiProvider(api_key=settings.google_api_key)
            llm_router.register_provider("gemini", gemini_provider)

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

            logger.info(
                "run_analysis_complete",
                meeting_id=meeting_id,
                analysis_id=str(analysis.id),
                call_type=effective_call_type,
            )
            return str(analysis.id)

    return run_async(_analyze())


@celery_app.task(base=BaseTask, bind=True, queue="analysis")
def rerun_analysis(self, analysis_id: str, requested_by: str) -> str:
    """Re-run an existing analysis, creating a new version."""

    async def _rerun():
        settings = get_settings()

        # First, look up the original analysis to find its org_id
        async with get_task_session() as session:
            llm_router = LLMRouter()
            gemini_provider = GeminiProvider(api_key=settings.google_api_key)
            llm_router.register_provider("gemini", gemini_provider)
            analysis_svc = AnalysisService(db=session, llm_router=llm_router)
            original = await analysis_svc.get_analysis(UUID(analysis_id))
            org_id = str(original.org_id)
            original_meeting_id = original.meeting_id
            original_call_type = original.call_type

        # Re-run with RLS scoped to the org
        async with get_task_session(org_id) as session:
            llm_router = LLMRouter()
            gemini_provider = GeminiProvider(api_key=settings.google_api_key)
            llm_router.register_provider("gemini", gemini_provider)

            analysis_svc = AnalysisService(db=session, llm_router=llm_router)

            new_analysis = await analysis_svc.run_analysis(
                meeting_id=original_meeting_id,
                org_id=UUID(org_id),
                call_type=original_call_type,
                requested_by=UUID(requested_by),
            )

            logger.info(
                "rerun_analysis_complete",
                original_analysis_id=analysis_id,
                new_analysis_id=str(new_analysis.id),
                call_type=original_call_type,
            )
            return str(new_analysis.id)

    return run_async(_rerun())
