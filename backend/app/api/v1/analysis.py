from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db_with_rls
from app.integrations.aws.s3 import get_s3_client
from app.llm.router import LLMRouter
from app.models.user import User
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import AnalysisService
from app.services.deal_service import DealService
from app.services.meeting_service import MeetingService
from app.tasks.analysis import run_analysis as run_analysis_task
from app.tasks.pipelines import create_reanalysis_pipeline

router = APIRouter()


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> list[AnalysisResponse]:
    """List all analyses for a meeting. Requires deal membership."""
    # Verify deal access through the meeting
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    llm_router = LLMRouter()
    service = AnalysisService(db, llm_router)
    analyses = await service.list_analyses(meeting_id)
    return [AnalysisResponse.model_validate(a) for a in analyses]


@router.post("", response_model=AnalysisResponse, status_code=202)
async def run_analysis(
    meeting_id: UUID,
    payload: AnalysisRequest,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    """Run a new analysis on a meeting. Requires run_analysis permission."""
    # Get the meeting to find org_id and verify access
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    # Create a placeholder analysis record so we can return an ID
    llm_router = LLMRouter()
    service = AnalysisService(db, llm_router)
    analysis = await service._next_version(meeting_id, payload.call_type)
    from app.models.analysis import Analysis

    analysis_record = Analysis(
        meeting_id=meeting_id,
        org_id=meeting.org_id,
        call_type=payload.call_type,
        model_used="",
        prompt_version="v1",
        status="queued",
        requested_by=current_user.id,
        version=analysis,
    )
    db.add(analysis_record)
    await db.flush()
    await db.commit()

    # Trigger Celery task (must be after commit so the worker can find the record)
    run_analysis_task.delay(str(meeting_id), payload.call_type, str(current_user.id))

    return AnalysisResponse.model_validate(analysis_record)


@router.get("/latest", response_model=AnalysisResponse)
async def get_latest_analysis(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    """Get the most recent analysis for a meeting."""
    # Verify deal access through the meeting
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    llm_router = LLMRouter()
    service = AnalysisService(db, llm_router)
    # Get the latest completed analysis of any type (most recent by created_at)
    analyses = await service.list_analyses(meeting_id)
    if not analyses:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Analysis", f"meeting={meeting_id}")
    return AnalysisResponse.model_validate(analyses[0])


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    meeting_id: UUID,
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    """Get a specific analysis by ID."""
    # Verify deal access through the meeting
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    llm_router = LLMRouter()
    service = AnalysisService(db, llm_router)
    analysis = await service.get_analysis(analysis_id)
    if analysis.meeting_id != meeting_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Analysis", str(analysis_id))
    return AnalysisResponse.model_validate(analysis)


@router.post("/{analysis_id}/rerun", response_model=AnalysisResponse, status_code=201)
async def rerun_analysis(
    meeting_id: UUID,
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    """Re-run an analysis, creating a new version. Requires run_analysis permission."""
    # Verify deal access through the meeting
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    # Get the original analysis to know its call_type
    llm_router = LLMRouter()
    service = AnalysisService(db, llm_router)
    original = await service.get_analysis(analysis_id)

    # Trigger the reanalysis pipeline
    create_reanalysis_pipeline(
        str(meeting_id), original.call_type, str(current_user.id)
    ).delay()

    # Create a placeholder record
    next_version = await service._next_version(meeting_id, original.call_type)
    from app.models.analysis import Analysis

    analysis_record = Analysis(
        meeting_id=meeting_id,
        org_id=meeting.org_id,
        call_type=original.call_type,
        model_used="",
        prompt_version="v1",
        status="queued",
        requested_by=current_user.id,
        version=next_version,
    )
    db.add(analysis_record)
    await db.flush()
    await db.commit()

    return AnalysisResponse.model_validate(analysis_record)
