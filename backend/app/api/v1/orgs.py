from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import OrgRole, verify_org_membership
from app.dependencies import get_current_user, get_db
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.schemas.organization import (
    OrgCreate,
    OrgMemberCreate,
    OrgMemberResponse,
    OrgResponse,
    OrgUpdate,
)
from app.services.auth_service import AuthService
from app.services.org_service import OrgService
from app.integrations.aws.cognito import get_cognito_client

router = APIRouter()


@router.get("", response_model=list[OrgResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrgResponse]:
    """List organizations the current user belongs to."""
    service = OrgService(db)
    orgs = await service.list_user_orgs(current_user.id)
    return [OrgResponse.model_validate(o) for o in orgs]


@router.post("", response_model=OrgResponse, status_code=201)
async def create_organization(
    payload: OrgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgResponse:
    """Create a new organization. Creator becomes owner."""
    service = OrgService(db)
    org = await service.create_org(
        name=payload.name,
        slug=payload.slug,
        domain=payload.domain,
        creator_id=current_user.id,
    )
    return OrgResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgResponse:
    """Get organization details. Requires membership."""
    await verify_org_membership(db, current_user.id, org_id)
    service = OrgService(db)
    org = await service.get_org(org_id)
    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: UUID,
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgResponse:
    """Update organization. Requires admin or owner role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)
    service = OrgService(db)
    org = await service.update_org(
        org_id,
        **payload.model_dump(exclude_unset=True),
    )
    return OrgResponse.model_validate(org)


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
async def list_org_members(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrgMemberResponse]:
    """List members of an organization."""
    await verify_org_membership(db, current_user.id, org_id)
    service = OrgService(db)
    members = await service.list_members(org_id)
    return [
        OrgMemberResponse(
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post("/{org_id}/members", response_model=OrgMemberResponse, status_code=201)
async def add_org_member(
    org_id: UUID,
    payload: OrgMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgMemberResponse:
    """Invite a user to the organization. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)
    auth_service = AuthService(db=db, cognito=get_cognito_client())
    user = await auth_service.get_user_by_email(payload.email)
    if user is None:
        raise NotFoundError("User", payload.email)

    service = OrgService(db)
    membership = await service.add_member(
        org_id=org_id,
        user_id=user.id,
        role=payload.role,
    )
    return OrgMemberResponse(
        user_id=membership.user_id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.patch("/{org_id}/members/{user_id}", response_model=OrgMemberResponse)
async def update_org_member_role(
    org_id: UUID,
    user_id: UUID,
    payload: OrgMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgMemberResponse:
    """Update a member's role. Requires owner role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.OWNER)
    service = OrgService(db)
    membership = await service.update_member_role(
        org_id=org_id,
        user_id=user_id,
        role=payload.role,
    )
    # Reload to get user info
    members = await service.list_members(org_id)
    for m in members:
        if m.user_id == user_id:
            return OrgMemberResponse(
                user_id=m.user_id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=m.role,
                joined_at=m.joined_at,
            )
    return OrgMemberResponse(
        user_id=membership.user_id,
        email="",
        full_name="",
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_org_member(
    org_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a member from the organization. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)

    # Check if this is the last owner
    owner_count = await db.scalar(
        select(func.count()).where(
            OrgMembership.org_id == org_id,
            OrgMembership.role == "owner",
        )
    )
    member = await db.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
    )
    if member and member.role == "owner" and owner_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last owner of the organization",
        )

    service = OrgService(db)
    await service.remove_member(org_id=org_id, user_id=user_id)
