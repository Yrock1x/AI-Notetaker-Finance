from datetime import datetime
from uuid import UUID

from app.schemas.common import BaseSchema


class UserResponse(BaseSchema):
    id: UUID
    email: str
    full_name: str
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime


class UserUpdate(BaseSchema):
    full_name: str | None = None
    avatar_url: str | None = None
