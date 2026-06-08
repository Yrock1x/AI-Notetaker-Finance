"""Organizations REST API — membership listing (worker-owned SQLite)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal
from app.db.models import Organization, OrgMembership, Profile
from app.db.scope import Principal, require_org
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class OrgResponse(BaseSchema):
    id: str
    name: str
    slug: str
    role: str


class OrgMemberResponse(BaseSchema):
    user_id: str
    role: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None


# ---- routes ---------------------------------------------------------------
@router.get("/orgs", response_model=list[OrgResponse])
def list_orgs(
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[OrgResponse]:
    rows = session.execute(
        select(Organization, OrgMembership.role)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .where(OrgMembership.user_id == principal.user_id)
    ).all()
    return [
        OrgResponse(id=org.id, name=org.name, slug=org.slug, role=role)
        for org, role in rows
    ]


@router.get("/orgs/{org_id}/members", response_model=list[OrgMemberResponse])
def list_org_members(
    org_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[OrgMemberResponse]:
    require_org(principal, org_id)
    rows = session.execute(
        select(OrgMembership, Profile)
        .join(Profile, Profile.id == OrgMembership.user_id)
        .where(OrgMembership.org_id == org_id)
    ).all()
    return [
        OrgMemberResponse(
            user_id=m.user_id,
            role=m.role,
            email=p.email,
            full_name=p.full_name,
            avatar_url=p.avatar_url,
        )
        for m, p in rows
    ]
