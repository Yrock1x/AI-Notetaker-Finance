from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import BaseSchema


class IntegrationResponse(BaseSchema):
    platform: str
    is_active: bool
    scopes: str | None = None
    connected_at: datetime


class OAuthInitResponse(BaseSchema):
    authorization_url: str


class BotSessionCreate(BaseSchema):
    meeting_url: str
    platform: Literal["zoom", "teams", "google_meet"]
    scheduled_start: datetime | None = None
    deal_id: UUID


class BotSessionResponse(BaseSchema):
    id: UUID
    deal_id: UUID
    platform: str
    meeting_url: str
    status: str
    scheduled_start: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    consent_obtained: bool
    created_at: datetime


class WebhookResponse(BaseSchema):
    received: bool = True
