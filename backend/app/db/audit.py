"""Audit log writes — small shared helper used by the store routers.

The recent-activity feed reads ``audit_logs``; these helpers populate it. Org
isolation is the caller's responsibility (pass an org the principal belongs to).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record_audit(
    session: Session,
    *,
    org_id: str,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    deal_id: str | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            deal_id=deal_id,
            details=details,
        )
    )
