"""Shared helpers for the store routers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_db, get_principal
from app.db.models import Deal, Meeting
from app.db.scope import AccessDenied, Principal

__all__ = [
    "get_db",
    "get_principal",
    "AccessDenied",
    "Principal",
    "scoped_deal_or_404",
    "scoped_meeting_or_404",
    "access_denied_handler",
]


def scoped_deal_or_404(session: Session, principal: Principal, deal_id: str) -> Deal:
    """Fetch a deal the principal can see (org member, not soft-deleted)."""
    deal = session.scalar(
        select(Deal).where(Deal.id == deal_id, Deal.deleted_at.is_(None))
    )
    if deal is None or not principal.in_org(deal.org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


def scoped_meeting_or_404(session: Session, principal: Principal, meeting_id: str) -> Meeting:
    meeting = session.scalar(select(Meeting).where(Meeting.id == meeting_id))
    if meeting is None or not principal.in_org(meeting.org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    return meeting


def access_denied_handler(_request, exc: Exception):  # noqa: ANN001 — registered on the app for AccessDenied
    """Map app-layer scope violations to 403 (registered on the app)."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


# re-exported for routers that want the dependency objects directly
_db_dep = Depends(get_db)
_principal_dep = Depends(get_principal)
