from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.common import BaseSchema


class AuditLogResponse(BaseSchema):
    id: UUID
    org_id: UUID
    user_id: UUID | None = None
    deal_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime


class AuditLogQuery(BaseSchema):
    user_id: UUID | None = None
    deal_id: UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
