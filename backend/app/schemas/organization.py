from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class OrgCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    domain: str | None = None


class OrgUpdate(BaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    domain: str | None = None
    settings: dict | None = None


class OrgResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    domain: str | None = None
    settings: dict | None = None
    created_at: datetime


class OrgMemberResponse(BaseSchema):
    user_id: UUID
    email: str
    full_name: str
    role: str
    joined_at: datetime


class OrgMemberCreate(BaseSchema):
    email: str
    role: Literal["owner", "admin", "member"] = "member"
