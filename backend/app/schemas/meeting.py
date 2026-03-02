from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class MeetingCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    meeting_date: datetime | None = None
    source: Literal["upload", "zoom", "teams", "bot", "slack"] = "upload"


class MeetingUpdate(BaseSchema):
    title: str | None = Field(None, min_length=1, max_length=500)
    meeting_date: datetime | None = None
    bot_enabled: bool | None = None


class MeetingResponse(BaseSchema):
    id: UUID
    deal_id: UUID
    org_id: UUID
    title: str
    meeting_date: datetime | None = None
    duration_seconds: int | None = None
    source: str
    status: str
    error_message: str | None = None
    bot_enabled: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class MeetingUploadResponse(BaseSchema):
    meeting_id: UUID
    upload_url: str
    file_key: str


class MeetingParticipantResponse(BaseSchema):
    id: UUID
    speaker_label: str
    speaker_name: str | None = None
    user_id: UUID | None = None


class UpdateSpeakerName(BaseSchema):
    speaker_label: str
    speaker_name: str
