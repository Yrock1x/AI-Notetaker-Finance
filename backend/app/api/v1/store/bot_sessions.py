"""Meeting bot sessions REST API (worker-owned SQLite, app-layer scoping)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.db.models import MeetingBotSession
from app.db.scope import Principal, org_scoped
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class BotSessionCreate(BaseSchema):
    deal_id: str
    platform: str
    meeting_url: str
    scheduled_start: datetime | None = None
    consent_obtained: bool = False


class BotSessionResponse(BaseSchema):
    id: str
    org_id: str
    deal_id: str
    meeting_id: str | None = None
    platform: str
    meeting_url: str
    status: str
    scheduled_start: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    recording_file_key: str | None = None
    recall_bot_id: str | None = None
    live_transcript_channel: str | None = None
    consent_obtained: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


# ---- routes ---------------------------------------------------------------
@router.get("/bot-sessions", response_model=list[BotSessionResponse])
def list_bot_sessions(
    deal_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[BotSessionResponse]:
    stmt = org_scoped(select(MeetingBotSession), MeetingBotSession, principal)
    if deal_id:
        stmt = stmt.where(MeetingBotSession.deal_id == deal_id)
    if status_filter:
        stmt = stmt.where(MeetingBotSession.status == status_filter)
    stmt = stmt.order_by(MeetingBotSession.created_at.desc())
    rows = session.scalars(stmt).all()
    return [BotSessionResponse.model_validate(r) for r in rows]


@router.post(
    "/bot-sessions",
    response_model=BotSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bot_session(
    payload: BotSessionCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> BotSessionResponse:
    deal = scoped_deal_or_404(session, principal, payload.deal_id)
    bot_session = MeetingBotSession(
        org_id=deal.org_id,
        deal_id=deal.id,
        platform=payload.platform,
        meeting_url=payload.meeting_url,
        status="scheduled",
        scheduled_start=(
            payload.scheduled_start.isoformat() if payload.scheduled_start else None
        ),
        consent_obtained=payload.consent_obtained,
        created_by=principal.user_id,
    )
    session.add(bot_session)
    session.flush()
    return BotSessionResponse.model_validate(bot_session)


@router.post("/bot-sessions/{session_id}/cancel", response_model=BotSessionResponse)
def cancel_bot_session(
    session_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> BotSessionResponse:
    bot_session = session.get(MeetingBotSession, session_id)
    if bot_session is None or not principal.in_org(bot_session.org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bot session not found"
        )
    bot_session.status = "cancelled"
    session.flush()
    return BotSessionResponse.model_validate(bot_session)
