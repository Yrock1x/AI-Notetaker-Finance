from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import DealRole
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.integrations.aws.s3 import get_s3_client
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.meeting import (
    MeetingCreate,
    MeetingResponse,
    MeetingUpdate,
    MeetingUploadResponse,
)
from app.services.deal_service import DealService
from app.services.meeting_service import MeetingService
from app.tasks.pipelines import create_meeting_pipeline

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[MeetingResponse])
async def list_meetings(
    deal_id: UUID,
    status: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[MeetingResponse]:
    """List meetings in a deal. Requires deal membership."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)
    result = await service.list_meetings(
        deal_id=deal_id,
        cursor=cursor,
        limit=limit,
        status_filter=status,
    )
    items = [MeetingResponse.model_validate(m) for m in result["items"]]
    return PaginatedResponse(
        items=items,
        cursor=result["cursor"],
        has_more=result["has_more"],
    )


@router.post("/upload", response_model=MeetingUploadResponse, status_code=201)
async def initiate_meeting_upload(
    deal_id: UUID,
    payload: MeetingCreate,
    content_type: str = Query(description="MIME type of the file to upload"),
    file_name: str = Query(description="Original file name"),
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> MeetingUploadResponse:
    """Get a presigned URL to upload a meeting recording. Requires write permission."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.ANALYST)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)

    # Generate presigned upload URL
    presigned = await service.generate_presigned_upload_url(
        org_id=org_id,
        deal_id=deal_id,
        filename=file_name,
        content_type=content_type,
    )

    # Create meeting record in 'uploading' status
    meeting = await service.create_meeting_from_upload(
        deal_id=deal_id,
        org_id=org_id,
        title=payload.title,
        uploaded_by=current_user.id,
        s3_key=presigned["s3_key"],
        meeting_date=payload.meeting_date,
    )

    return MeetingUploadResponse(
        meeting_id=meeting.id,
        upload_url=presigned["upload_url"],
        file_key=presigned["s3_key"],
    )


@router.post("/upload/{meeting_id}/confirm", response_model=MeetingResponse)
async def confirm_meeting_upload(
    deal_id: UUID,
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> MeetingResponse:
    """Confirm that a meeting file upload is complete. Triggers processing pipeline."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.ANALYST)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)

    # Update status from 'uploading' to 'transcribing'
    meeting = await service.update_meeting_status(meeting_id, "transcribing")

    # Trigger the Celery processing pipeline
    create_meeting_pipeline(str(meeting_id), str(org_id)).delay()

    return MeetingResponse.model_validate(meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    deal_id: UUID,
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> MeetingResponse:
    """Get meeting details. Requires deal membership."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)
    meeting = await service.get_meeting(meeting_id)
    if meeting.deal_id != deal_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Meeting", str(meeting_id))
    return MeetingResponse.model_validate(meeting)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    deal_id: UUID,
    meeting_id: UUID,
    payload: MeetingUpdate,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> MeetingResponse:
    """Update meeting metadata. Requires write permission."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.ANALYST)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)
    # Verify meeting belongs to this deal
    existing = await service.get_meeting(meeting_id)
    if existing.deal_id != deal_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Meeting", str(meeting_id))
    meeting = await service.update_meeting(
        meeting_id=meeting_id,
        title=payload.title,
        meeting_date=payload.meeting_date,
        bot_enabled=payload.bot_enabled,
    )
    return MeetingResponse.model_validate(meeting)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    deal_id: UUID,
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a meeting and its associated data. Requires delete permission."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.LEAD)

    settings = get_settings()
    s3_client = get_s3_client()
    service = MeetingService(db, s3_client, settings)
    meeting = await service.get_meeting(meeting_id)
    if meeting.deal_id != deal_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Meeting", str(meeting_id))
    await service.delete_meeting(meeting_id)
