from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db_with_rls
from app.integrations.aws.s3 import get_s3_client
from app.models.user import User
from app.schemas.meeting import MeetingParticipantResponse, UpdateSpeakerName
from app.schemas.transcript import TranscriptResponse, TranscriptSegmentResponse
from app.services.deal_service import DealService
from app.services.meeting_service import MeetingService
from app.services.transcript_service import TranscriptService

router = APIRouter()


async def _check_meeting_deal_access(
    meeting_id: UUID, user_id: UUID, db: AsyncSession
) -> None:
    """Load the meeting to find its deal_id, then verify deal access."""
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)
    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, user_id)


@router.get("", response_model=TranscriptResponse)
async def get_transcript(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> TranscriptResponse:
    """Get the full transcript for a meeting. Requires deal membership."""
    await _check_meeting_deal_access(meeting_id, current_user.id, db)

    service = TranscriptService(db)
    transcript = await service.get_transcript(meeting_id)
    return TranscriptResponse.model_validate(transcript)


@router.get("/segments", response_model=list[TranscriptSegmentResponse])
async def get_transcript_segments(
    meeting_id: UUID,
    speaker: str | None = Query(None, description="Filter by speaker label"),
    from_time: float | None = Query(None, description="Start time in seconds"),
    to_time: float | None = Query(None, description="End time in seconds"),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> list[TranscriptSegmentResponse]:
    """Get transcript segments with optional filters."""
    await _check_meeting_deal_access(meeting_id, current_user.id, db)

    service = TranscriptService(db)
    transcript = await service.get_transcript(meeting_id)
    segments = await service.get_segments(
        transcript_id=transcript.id,
        speaker=speaker,
        start_time=from_time,
        end_time=to_time,
    )
    return [TranscriptSegmentResponse.model_validate(s) for s in segments]


@router.get("/search", response_model=list[TranscriptSegmentResponse])
async def search_transcript(
    meeting_id: UUID,
    q: str = Query(min_length=1, description="Search query"),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> list[TranscriptSegmentResponse]:
    """Full-text search within a transcript."""
    await _check_meeting_deal_access(meeting_id, current_user.id, db)

    service = TranscriptService(db)
    transcript = await service.get_transcript(meeting_id)
    segments = await service.search_transcript(
        transcript_id=transcript.id,
        query=q,
    )
    return [TranscriptSegmentResponse.model_validate(s) for s in segments]


@router.get("/participants", response_model=list[MeetingParticipantResponse])
async def get_participants(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> list[MeetingParticipantResponse]:
    """Get identified participants/speakers for a meeting."""
    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting_with_details(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(meeting.deal_id, current_user.id)

    return [MeetingParticipantResponse.model_validate(p) for p in meeting.participants]


@router.patch("/participants", response_model=MeetingParticipantResponse)
async def update_speaker_name(
    meeting_id: UUID,
    payload: UpdateSpeakerName,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> MeetingParticipantResponse:
    """Update a speaker's display name. Requires write permission."""
    from app.core.security import DealRole

    settings = get_settings()
    s3_client = get_s3_client()
    meeting_service = MeetingService(db, s3_client, settings)
    meeting = await meeting_service.get_meeting(meeting_id)

    deal_service = DealService(db)
    await deal_service.check_deal_access(
        meeting.deal_id, current_user.id, min_role=DealRole.ANALYST,
    )

    service = TranscriptService(db)
    transcript = await service.get_transcript(meeting_id)
    await service.update_speaker_name(
        transcript_id=transcript.id,
        old_name=payload.speaker_label,
        new_name=payload.speaker_name,
    )

    # Reload the meeting with participants to return the updated participant
    meeting = await meeting_service.get_meeting_with_details(meeting_id)
    for p in meeting.participants:
        if p.speaker_label == payload.speaker_label:
            return MeetingParticipantResponse.model_validate(p)

    # If no matching participant found, return the first one that was updated
    # (the speaker_label may be in segments but not in participants table)
    return MeetingParticipantResponse(
        id=meeting.id,
        speaker_label=payload.speaker_label,
        speaker_name=payload.speaker_name,
    )
