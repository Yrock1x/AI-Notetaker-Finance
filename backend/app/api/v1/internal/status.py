"""/internal/* — Meeting status updates from Inngest pipeline steps."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.internal._common import (
    require_internal_token,
)
from app.db.deps import get_db
from app.db.models import (
    Meeting,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# /internal/meeting-status — let Inngest functions flip a meeting's status
# (and record an error) as a pipeline progresses or fails.
# ---------------------------------------------------------------------------
class MeetingStatusRequest(BaseModel):
    meeting_id: str
    status: str
    error_message: str | None = None


class MeetingStatusResponse(BaseModel):
    ok: bool


@router.post(
    "/meeting-status",
    response_model=MeetingStatusResponse,
    dependencies=[Depends(require_internal_token)],
)
async def set_meeting_status(
    body: MeetingStatusRequest,
    session: Session = Depends(get_db),
) -> MeetingStatusResponse:
    meeting = session.get(Meeting, body.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.status = body.status
    if body.error_message is not None:
        meeting.error_message = body.error_message
    session.flush()
    return MeetingStatusResponse(ok=True)
