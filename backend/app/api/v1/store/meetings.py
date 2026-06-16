"""Meetings REST API (replaces frontend direct Supabase access).

Follows the deals.py reference: scoped reads via app/db/scope, single-row
fetches via scoped_*_or_404. No RLS — every query is org/meeting scoped here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import (
    get_db,
    get_principal,
    scoped_deal_or_404,
    scoped_meeting_or_404,
)
from app.db.models import Deal, Meeting
from app.db.scope import Principal, org_scoped
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class MeetingResponse(BaseSchema):
    id: str
    org_id: str
    deal_id: str | None = None
    title: str
    meeting_date: datetime | None = None
    duration_seconds: int | None = None
    source: str
    source_url: str | None = None
    file_key: str | None = None
    status: str
    error_message: str | None = None
    bot_enabled: bool
    external_event_id: str | None = None
    external_provider: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class MeetingUpdate(BaseSchema):
    title: str | None = None
    meeting_date: datetime | None = None
    bot_enabled: bool | None = None
    deal_id: str | None = None


class MeetingCreate(BaseSchema):
    title: str
    source: str = "upload"
    file_key: str | None = None
    source_url: str | None = None
    meeting_date: datetime | None = None
    duration_seconds: int | None = None
    bot_enabled: bool = True


class DealRef(BaseSchema):
    id: str
    name: str


class CalendarMeetingResponse(BaseSchema):
    id: str
    org_id: str
    deal_id: str | None = None
    title: str
    meeting_date: datetime | None = None
    duration_seconds: int | None = None
    source: str
    source_url: str | None = None
    file_key: str | None = None
    status: str
    error_message: str | None = None
    bot_enabled: bool
    external_event_id: str | None = None
    external_provider: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    deal: DealRef | None = None


# ---- endpoints ------------------------------------------------------------
@router.get("/deals/{deal_id}/meetings", response_model=list[MeetingResponse])
def list_deal_meetings(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[MeetingResponse]:
    scoped_deal_or_404(session, principal, deal_id)
    rows = session.scalars(
        select(Meeting)
        .where(Meeting.deal_id == deal_id)
        .order_by(Meeting.created_at.desc())
    ).all()
    return [MeetingResponse.model_validate(m) for m in rows]


@router.post(
    "/deals/{deal_id}/meetings",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_meeting(
    deal_id: str,
    payload: MeetingCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> MeetingResponse:
    """Create a meeting under a deal (used by the upload-confirm flow)."""
    deal = scoped_deal_or_404(session, principal, deal_id)
    meeting = Meeting(
        org_id=deal.org_id,
        deal_id=deal.id,
        title=payload.title,
        source=payload.source,
        file_key=payload.file_key,
        source_url=payload.source_url,
        meeting_date=payload.meeting_date.isoformat() if payload.meeting_date else None,
        duration_seconds=payload.duration_seconds,
        bot_enabled=payload.bot_enabled,
        status="uploading",
        created_by=principal.user_id,
    )
    session.add(meeting)
    session.flush()
    return MeetingResponse.model_validate(meeting)


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> MeetingResponse:
    return MeetingResponse.model_validate(
        scoped_meeting_or_404(session, principal, meeting_id)
    )


@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: str,
    payload: MeetingUpdate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> MeetingResponse:
    meeting = scoped_meeting_or_404(session, principal, meeting_id)
    data = payload.model_dump(exclude_unset=True)
    # A client-supplied deal_id must be a deal in the SAME org — never let a
    # meeting be reassigned to another tenant's deal (IDOR).
    if "deal_id" in data and data["deal_id"] is not None:
        target = scoped_deal_or_404(session, principal, data["deal_id"])
        if target.org_id != meeting.org_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cross-org deal")
    for field, value in data.items():
        if field == "meeting_date" and value is not None:
            value = value.isoformat()
        setattr(meeting, field, value)
    session.flush()
    return MeetingResponse.model_validate(meeting)


@router.get("/calendar/meetings", response_model=list[CalendarMeetingResponse])
def calendar_meetings(
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[CalendarMeetingResponse]:
    stmt = (
        org_scoped(select(Meeting, Deal), Meeting, principal)
        .outerjoin(Deal, Deal.id == Meeting.deal_id)
        .order_by(Meeting.meeting_date)
    )
    rows = session.execute(stmt).all()
    out: list[CalendarMeetingResponse] = []
    for meeting, deal in rows:
        resp = CalendarMeetingResponse.model_validate(meeting)
        resp.deal = DealRef(id=deal.id, name=deal.name) if deal is not None else None
        out.append(resp)
    return out


@router.get(
    "/dashboard/upcoming-unassigned", response_model=list[MeetingResponse]
)
def upcoming_unassigned(
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[MeetingResponse]:
    stmt = (
        org_scoped(select(Meeting), Meeting, principal)
        .where(Meeting.deal_id.is_(None))
        .where(Meeting.external_provider.is_not(None))
        .order_by(Meeting.meeting_date)
    )
    rows = session.scalars(stmt).all()
    return [MeetingResponse.model_validate(m) for m in rows]
