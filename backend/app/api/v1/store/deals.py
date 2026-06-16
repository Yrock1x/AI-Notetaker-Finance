"""Deals + deal-members REST API (replaces frontend direct Supabase access).

Reference implementation for the store routers: scoped reads via app/db/scope,
org-membership checks on writes, soft-delete, cursor pagination, audit logging.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.db.audit import record_audit
from app.db.base import utcnow_iso
from app.db.models import Deal, DealMembership, OrgMembership, Profile
from app.db.scope import Principal, org_scoped, require_org
from app.schemas.common import BaseSchema, PaginatedResponse

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class DealCreate(BaseSchema):
    org_id: str
    name: str
    description: str | None = None
    target_company: str | None = None
    deal_type: str = "general"
    stage: str | None = None
    status: str = "active"


class DealUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    target_company: str | None = None
    deal_type: str | None = None
    stage: str | None = None
    status: str | None = None


class DealResponse(BaseSchema):
    id: str
    org_id: str
    name: str
    description: str | None = None
    target_company: str | None = None
    deal_type: str
    stage: str | None = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseSchema):
    user_id: str
    role: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None


class MemberCreate(BaseSchema):
    user_id: str
    role: str = "analyst"


# ---- deals ----------------------------------------------------------------
@router.get("", response_model=PaginatedResponse[DealResponse])
def list_deals(
    status_filter: str | None = Query(None, alias="status"),
    deal_type: str | None = Query(None),
    q: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> PaginatedResponse[DealResponse]:
    stmt = org_scoped(select(Deal), Deal, principal).where(Deal.deleted_at.is_(None))
    if status_filter:
        stmt = stmt.where(Deal.status == status_filter)
    if deal_type:
        stmt = stmt.where(Deal.deal_type == deal_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Deal.name.ilike(like), Deal.target_company.ilike(like)))
    if cursor:
        # Composite (created_at, id) cursor so rows sharing a created_at aren't
        # skipped/duplicated across a page boundary. Falls back to the legacy
        # created_at-only cursor for any URL minted before this change.
        c_created, sep, c_id = cursor.rpartition("|")
        if sep:
            stmt = stmt.where(tuple_(Deal.created_at, Deal.id) < (c_created, c_id))
        else:
            stmt = stmt.where(Deal.created_at < cursor)
    stmt = stmt.order_by(Deal.created_at.desc(), Deal.id.desc()).limit(limit + 1)

    rows = session.scalars(stmt).all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = (
        f"{items[-1].created_at}|{items[-1].id}" if has_more and items else None
    )
    return PaginatedResponse(
        items=[DealResponse.model_validate(d) for d in items],
        cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{deal_id}", response_model=DealResponse)
def get_deal(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> DealResponse:
    return DealResponse.model_validate(scoped_deal_or_404(session, principal, deal_id))


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> DealResponse:
    require_org(principal, payload.org_id)  # must be a member of the target org
    deal = Deal(
        org_id=payload.org_id,
        name=payload.name,
        description=payload.description,
        target_company=payload.target_company,
        deal_type=payload.deal_type,
        stage=payload.stage,
        status=payload.status,
        created_by=principal.user_id,
    )
    session.add(deal)
    session.flush()
    # creator is automatically a deal member (lead)
    session.add(
        DealMembership(
            deal_id=deal.id,
            user_id=principal.user_id,
            org_id=deal.org_id,
            role="lead",
            added_by=principal.user_id,
        )
    )
    record_audit(
        session,
        org_id=deal.org_id,
        user_id=principal.user_id,
        action="create",
        resource_type="deal",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"name": deal.name},
    )
    session.flush()
    return DealResponse.model_validate(deal)


@router.patch("/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: str,
    payload: DealUpdate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> DealResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(deal, field, value)
    record_audit(
        session,
        org_id=deal.org_id,
        user_id=principal.user_id,
        action="update",
        resource_type="deal",
        resource_id=deal.id,
        deal_id=deal.id,
    )
    session.flush()
    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    deal = scoped_deal_or_404(session, principal, deal_id)
    deal.deleted_at = utcnow_iso()
    record_audit(
        session,
        org_id=deal.org_id,
        user_id=principal.user_id,
        action="delete",
        resource_type="deal",
        resource_id=deal.id,
        deal_id=deal.id,
    )
    session.flush()


# ---- members --------------------------------------------------------------
@router.get("/{deal_id}/members", response_model=list[MemberResponse])
def list_members(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[MemberResponse]:
    scoped_deal_or_404(session, principal, deal_id)
    rows = session.execute(
        select(DealMembership, Profile)
        .join(Profile, Profile.id == DealMembership.user_id)
        .where(DealMembership.deal_id == deal_id)
    ).all()
    return [
        MemberResponse(
            user_id=m.user_id,
            role=m.role,
            email=p.email,
            full_name=p.full_name,
            avatar_url=p.avatar_url,
        )
        for m, p in rows
    ]


@router.post(
    "/{deal_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    deal_id: str,
    payload: MemberCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> MemberResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    # The target user must already belong to the deal's org — never add a
    # foreign-org user as a deal member (IDOR / cross-tenant association).
    in_org = session.scalar(
        select(OrgMembership.id).where(
            OrgMembership.org_id == deal.org_id,
            OrgMembership.user_id == payload.user_id,
        )
    )
    if not in_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this org"
        )
    existing = session.scalar(
        select(DealMembership).where(
            DealMembership.deal_id == deal_id, DealMembership.user_id == payload.user_id
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member")
    session.add(
        DealMembership(
            deal_id=deal_id,
            user_id=payload.user_id,
            org_id=deal.org_id,
            role=payload.role,
            added_by=principal.user_id,
        )
    )
    session.flush()
    profile = session.get(Profile, payload.user_id)
    return MemberResponse(
        user_id=payload.user_id,
        role=payload.role,
        email=profile.email if profile else None,
        full_name=profile.full_name if profile else None,
        avatar_url=profile.avatar_url if profile else None,
    )


@router.delete("/{deal_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    deal_id: str,
    user_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    scoped_deal_or_404(session, principal, deal_id)
    member = session.scalar(
        select(DealMembership).where(
            DealMembership.deal_id == deal_id, DealMembership.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    session.delete(member)
    session.flush()
