"""Dashboard + per-deal aggregate reads (activity feed, extractions, action items).

Follows the store-router pattern: scoped reads via app/db/scope, single-row
fetches via scoped_deal_or_404, app-layer org isolation (no RLS).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.db.base import utcnow_iso
from app.db.models import (
    ActionItemCompletion,
    Analysis,
    AuditLog,
    Deal,
    Meeting,
    Profile,
)
from app.db.scope import Principal, org_scoped
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class ActivityResponse(BaseSchema):
    id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    deal_id: str | None = None
    deal_name: str | None = None
    actor_name: str | None = None
    created_at: datetime
    details: dict | None = None


class ExtractionResponse(BaseSchema):
    id: str
    meeting_id: str
    call_type: str
    structured_output: dict | None = None
    created_at: datetime


class ActionItemResponse(BaseSchema):
    action_key: str
    action_text: str | None = None
    analysis_id: str
    completed_by: str
    completed_at: datetime


class ActionItemCreate(BaseSchema):
    analysis_id: str
    action_key: str
    action_text: str | None = None


# ---- activity feed --------------------------------------------------------
@router.get("/dashboard/activity", response_model=list[ActivityResponse])
def list_activity(
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[ActivityResponse]:
    stmt = (
        org_scoped(
            select(AuditLog, Profile.full_name, Deal.name), AuditLog, principal
        )
        .outerjoin(Profile, Profile.id == AuditLog.user_id)
        .outerjoin(Deal, Deal.id == AuditLog.deal_id)
        .order_by(AuditLog.created_at.desc())
        .limit(15)
    )
    rows = session.execute(stmt).all()
    return [
        ActivityResponse(
            id=log.id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            deal_id=log.deal_id,
            deal_name=deal_name,
            actor_name=actor_name,
            created_at=log.created_at,
            details=log.details,
        )
        for log, actor_name, deal_name in rows
    ]


# ---- extractions ----------------------------------------------------------
@router.get("/deals/{deal_id}/extractions", response_model=list[ExtractionResponse])
def list_extractions(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[ExtractionResponse]:
    scoped_deal_or_404(session, principal, deal_id)
    stmt = (
        select(Analysis)
        .join(Meeting, Meeting.id == Analysis.meeting_id)
        .where(Meeting.deal_id == deal_id, Analysis.status == "completed")
        .order_by(Analysis.created_at.desc())
    )
    rows = session.scalars(stmt).all()
    return [
        ExtractionResponse(
            id=a.id,
            meeting_id=a.meeting_id,
            call_type=a.call_type,
            structured_output=a.structured_output,
            created_at=a.created_at,
        )
        for a in rows
    ]


# ---- action items ---------------------------------------------------------
@router.get("/deals/{deal_id}/action-items", response_model=list[ActionItemResponse])
def list_action_items(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[ActionItemResponse]:
    scoped_deal_or_404(session, principal, deal_id)
    rows = session.scalars(
        select(ActionItemCompletion).where(ActionItemCompletion.deal_id == deal_id)
    ).all()
    return [ActionItemResponse.model_validate(r) for r in rows]


@router.post(
    "/deals/{deal_id}/action-items",
    response_model=ActionItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_action_item(
    deal_id: str,
    payload: ActionItemCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> ActionItemResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    # The referenced analysis must belong to the same org (no cross-tenant ref).
    analysis_org = session.scalar(
        select(Analysis.org_id).where(Analysis.id == payload.analysis_id)
    )
    if analysis_org != deal.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found in this deal's org"
        )
    existing = session.scalar(
        select(ActionItemCompletion).where(
            ActionItemCompletion.deal_id == deal_id,
            ActionItemCompletion.action_key == payload.action_key,
        )
    )
    if existing is not None:
        existing.analysis_id = payload.analysis_id
        existing.action_text = payload.action_text
        existing.completed_by = principal.user_id
        # Refresh the timestamp — re-completing should reflect the latest action,
        # not the original (the column default only fires on insert).
        existing.completed_at = utcnow_iso()
        row = existing
    else:
        row = ActionItemCompletion(
            org_id=deal.org_id,
            deal_id=deal_id,
            analysis_id=payload.analysis_id,
            action_key=payload.action_key,
            action_text=payload.action_text,
            completed_by=principal.user_id,
        )
        session.add(row)
    session.flush()
    return ActionItemResponse.model_validate(row)


@router.delete(
    "/deals/{deal_id}/action-items/{action_key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_action_item(
    deal_id: str,
    action_key: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    scoped_deal_or_404(session, principal, deal_id)
    row = session.scalar(
        select(ActionItemCompletion).where(
            ActionItemCompletion.deal_id == deal_id,
            ActionItemCompletion.action_key == action_key,
        )
    )
    if row is not None:
        session.delete(row)
        session.flush()
