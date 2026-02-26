from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class DealCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_company: str | None = None
    deal_type: str = "general"  # m_and_a, pe, vc, debt, general
    stage: str | None = None


class DealUpdate(BaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    target_company: str | None = None
    deal_type: str | None = None
    stage: str | None = None
    status: str | None = None  # active, closed, archived


class DealResponse(BaseSchema):
    id: UUID
    org_id: UUID
    name: str
    description: str | None = None
    target_company: str | None = None
    deal_type: str
    stage: str | None = None
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class DealMemberCreate(BaseSchema):
    user_id: UUID
    role: str = "analyst"  # lead, admin, analyst, viewer


class DealMemberResponse(BaseSchema):
    user_id: UUID
    email: str | None = None
    full_name: str | None = None
    role: str
    added_at: datetime
