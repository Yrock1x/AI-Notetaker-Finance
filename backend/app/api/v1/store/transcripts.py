"""Transcript / segments / participants / chat read-only REST API.

These tables hang off a meeting. transcript_segments, meeting_participants and
meeting_chat_messages have NO org_id, so tenant isolation is enforced by first
resolving the parent meeting via ``scoped_meeting_or_404`` (which 404s if the
principal is not in the meeting's org) and only then querying by meeting_id.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_meeting_or_404
from app.db.models import (
    MeetingChatMessage,
    MeetingParticipant,
    Transcript,
    TranscriptSegment,
)
from app.db.scope import Principal
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class TranscriptResponse(BaseSchema):
    id: str
    full_text: str
    language: str
    word_count: int
    confidence_score: float | None = None
    created_at: datetime


class SegmentResponse(BaseSchema):
    id: str
    meeting_id: str
    speaker_label: str
    speaker_name: str | None = None
    text: str
    start_time: float
    end_time: float
    confidence: float | None = None
    segment_index: int
    is_partial: bool


class ParticipantResponse(BaseSchema):
    id: str
    meeting_id: str
    speaker_label: str
    speaker_name: str | None = None
    user_id: str | None = None
    email_address: str | None = None
    joined_at: datetime | None = None
    left_at: datetime | None = None


class ChatMessageResponse(BaseSchema):
    id: str
    meeting_id: str
    sender_name: str | None = None
    sender_email: str | None = None
    text: str
    sent_at: datetime


# ---- transcript -----------------------------------------------------------
@router.get("/meetings/{meeting_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    meeting_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> TranscriptResponse:
    scoped_meeting_or_404(session, principal, meeting_id)
    transcript = session.scalar(
        select(Transcript).where(Transcript.meeting_id == meeting_id)
    )
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    return TranscriptResponse.model_validate(transcript)


# ---- segments -------------------------------------------------------------
@router.get(
    "/meetings/{meeting_id}/transcript-segments",
    response_model=list[SegmentResponse],
)
def list_transcript_segments(
    meeting_id: str,
    speaker: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[SegmentResponse]:
    scoped_meeting_or_404(session, principal, meeting_id)
    stmt = select(TranscriptSegment).where(
        TranscriptSegment.meeting_id == meeting_id,
        TranscriptSegment.is_partial.is_(False),
    )
    if speaker:
        stmt = stmt.where(TranscriptSegment.speaker_label == speaker)
    if q:
        stmt = stmt.where(TranscriptSegment.text.ilike(f"%{q}%"))
    stmt = stmt.order_by(TranscriptSegment.start_time).limit(limit)
    rows = session.scalars(stmt).all()
    return [SegmentResponse.model_validate(r) for r in rows]


# ---- participants ---------------------------------------------------------
@router.get(
    "/meetings/{meeting_id}/participants",
    response_model=list[ParticipantResponse],
)
def list_participants(
    meeting_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[ParticipantResponse]:
    scoped_meeting_or_404(session, principal, meeting_id)
    stmt = (
        select(MeetingParticipant)
        .where(MeetingParticipant.meeting_id == meeting_id)
        .order_by(MeetingParticipant.joined_at.is_(None), MeetingParticipant.joined_at)
    )
    rows = session.scalars(stmt).all()
    return [ParticipantResponse.model_validate(r) for r in rows]


# ---- chat -----------------------------------------------------------------
@router.get("/meetings/{meeting_id}/chat", response_model=list[ChatMessageResponse])
def list_chat(
    meeting_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[ChatMessageResponse]:
    scoped_meeting_or_404(session, principal, meeting_id)
    stmt = (
        select(MeetingChatMessage)
        .where(MeetingChatMessage.meeting_id == meeting_id)
        .order_by(MeetingChatMessage.sent_at)
        .limit(500)
    )
    rows = session.scalars(stmt).all()
    return [ChatMessageResponse.model_validate(r) for r in rows]
