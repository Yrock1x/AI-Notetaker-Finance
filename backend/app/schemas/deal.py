from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import BaseSchema


class DealCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_company: str | None = None
    deal_type: Literal[
        "buyout", "growth_equity", "venture", "recapitalization", "add_on", "other",
        "m_and_a", "pe", "vc", "debt", "general",
    ] = "other"
    stage: str | None = None


class DealUpdate(BaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    target_company: str | None = None
    deal_type: str | None = None
    stage: str | None = None
    status: Literal["active", "closed", "archived"] | None = None


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
    """Add a user to a deal by user_id or by email.

    When ``email`` is supplied and the user doesn't exist yet, the backend
    creates a placeholder row that gets linked to the real Cognito subject
    on first sign-in. At least one of ``user_id`` or ``email`` must be set.
    """

    user_id: UUID | None = None
    email: str | None = None
    role: Literal["lead", "admin", "analyst", "viewer"] = "analyst"

    @model_validator(mode="after")
    def _require_identifier(self) -> "DealMemberCreate":
        if self.user_id is None and not self.email:
            raise ValueError("Either user_id or email is required")
        return self


class DealMemberResponse(BaseSchema):
    user_id: UUID
    email: str | None = None
    full_name: str | None = None
    role: str
    added_at: datetime
