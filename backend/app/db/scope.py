"""App-layer multi-tenant scoping — the replacement for Postgres RLS.

Postgres enforced isolation in the engine via ``org_id in user_org_ids()``
policies. SQLite has none, so the equivalent lives here and **every** query that
serves a user must go through it. One module = one place to audit.

Usage:

    principal = load_principal(session, user_id)
    stmt = org_scoped(select(Deal), Deal, principal).where(Deal.deleted_at.is_(None))
    deals = session.scalars(stmt).all()

For the three hierarchy-scoped tables that have no ``org_id`` of their own
(transcript_segments, meeting_participants, meeting_chat_messages) use
``meeting_scoped`` which joins through meetings.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, false, select
from sqlalchemy.orm import Session

from app.db.models import Meeting, OrgMembership


class AccessDenied(Exception):  # noqa: N818 — established name, raised/caught across the app
    """Raised when a principal tries to touch data outside their orgs."""


@dataclass(frozen=True)
class Principal:
    """The authenticated user and the orgs they belong to (cached per request)."""

    user_id: str
    org_ids: tuple[str, ...]
    admin_org_ids: tuple[str, ...]

    def in_org(self, org_id: str | None) -> bool:
        return org_id in self.org_ids

    def is_admin_of(self, org_id: str | None) -> bool:
        return org_id in self.admin_org_ids


def load_principal(session: Session, user_id: str) -> Principal:
    """Load the user's org memberships once, for reuse across a request."""
    rows = session.execute(
        select(OrgMembership.org_id, OrgMembership.role).where(
            OrgMembership.user_id == user_id
        )
    ).all()
    org_ids = tuple(r[0] for r in rows)
    admin_org_ids = tuple(r[0] for r in rows if r[1] in ("owner", "admin"))
    return Principal(user_id=user_id, org_ids=org_ids, admin_org_ids=admin_org_ids)


# ---------------------------------------------------------------------------
# Query scoping
# ---------------------------------------------------------------------------
def org_scoped(stmt: Select, model, principal: Principal) -> Select:
    """Restrict an org-owned model's query to the principal's orgs."""
    if not principal.org_ids:
        return stmt.where(false())  # no memberships → see nothing
    return stmt.where(model.org_id.in_(principal.org_ids))


def meeting_scoped(stmt: Select, model, principal: Principal) -> Select:
    """Restrict a meeting-child model (no org_id) via its parent meeting."""
    if not principal.org_ids:
        return stmt.where(false())  # no memberships → see nothing
    visible_meetings = select(Meeting.id).where(Meeting.org_id.in_(principal.org_ids))
    return stmt.where(model.meeting_id.in_(visible_meetings))


# ---------------------------------------------------------------------------
# Imperative assertions (for writes / single-row fetches)
# ---------------------------------------------------------------------------
def require_org(principal: Principal, org_id: str | None) -> None:
    if not principal.in_org(org_id):
        raise AccessDenied(f"user {principal.user_id} not a member of org {org_id}")


def require_org_admin(principal: Principal, org_id: str | None) -> None:
    if not principal.is_admin_of(org_id):
        raise AccessDenied(f"user {principal.user_id} not an admin of org {org_id}")


def deal_org_id(session: Session, deal_id: str) -> str | None:
    """Look up a deal's org_id (for deriving org on writes)."""
    from app.db.models import Deal

    return session.scalar(select(Deal.org_id).where(Deal.id == deal_id))


def meeting_org_id(session: Session, meeting_id: str) -> str | None:
    return session.scalar(select(Meeting.org_id).where(Meeting.id == meeting_id))
