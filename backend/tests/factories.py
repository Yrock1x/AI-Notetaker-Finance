"""Factory Boy factories for generating test data."""

import uuid
from datetime import UTC, datetime

from app.models.deal import Deal
from app.models.meeting import Meeting
from app.models.organization import Organization
from app.models.user import User


def make_user(**overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "cognito_sub": f"cognito-{uuid.uuid4()}",
        "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
        "full_name": "Test User",
        "is_active": True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


def make_organization(**overrides) -> Organization:
    slug = f"org-{uuid.uuid4().hex[:8]}"
    defaults = {
        "id": uuid.uuid4(),
        "name": "Test Organization",
        "slug": slug,
    }
    defaults.update(overrides)
    org = Organization(**defaults)
    org.created_at = datetime.now(UTC)
    org.updated_at = datetime.now(UTC)
    return org


def make_deal(
    org_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    **overrides,
) -> Deal:
    defaults = {
        "id": uuid.uuid4(),
        "org_id": org_id or uuid.uuid4(),
        "name": "Test Deal",
        "deal_type": "m_and_a",
        "status": "active",
        "created_by": created_by or uuid.uuid4(),
    }
    defaults.update(overrides)
    deal = Deal(**defaults)
    deal.created_at = datetime.now(UTC)
    deal.updated_at = datetime.now(UTC)
    return deal


def make_meeting(
    deal_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    **overrides,
) -> Meeting:
    defaults = {
        "id": uuid.uuid4(),
        "deal_id": deal_id or uuid.uuid4(),
        "org_id": org_id or uuid.uuid4(),
        "title": "Test Meeting",
        "source": "upload",
        "status": "uploading",
        "created_by": created_by or uuid.uuid4(),
    }
    defaults.update(overrides)
    meeting = Meeting(**defaults)
    meeting.created_at = datetime.now(UTC)
    meeting.updated_at = datetime.now(UTC)
    return meeting
