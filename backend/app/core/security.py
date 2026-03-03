from enum import StrEnum
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class DealRole(StrEnum):
    LEAD = "lead"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Role hierarchy: higher index = more permissions
DEAL_ROLE_HIERARCHY: dict[DealRole, int] = {
    DealRole.VIEWER: 0,
    DealRole.ANALYST: 1,
    DealRole.ADMIN: 2,
    DealRole.LEAD: 3,
}

DEAL_ROLE_PERMISSIONS: dict[DealRole, set[str]] = {
    DealRole.LEAD: {
        "read", "write", "delete", "manage_members",
        "manage_settings", "run_analysis", "export",
    },
    DealRole.ADMIN: {"read", "write", "manage_members", "run_analysis", "export"},
    DealRole.ANALYST: {"read", "write", "run_analysis"},
    DealRole.VIEWER: {"read"},
}


async def verify_org_membership(
    db: AsyncSession,
    user_id: UUID,
    org_id: UUID,
    min_role: OrgRole | None = None,
) -> None:
    """Verify that a user belongs to an organization.

    Raises HTTPException 403 if the user is not a member or lacks the required role.
    """
    from app.models.org_membership import OrgMembership

    stmt = select(OrgMembership).where(
        OrgMembership.user_id == user_id,
        OrgMembership.org_id == org_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    if min_role is not None:
        org_role_hierarchy = {OrgRole.MEMBER: 0, OrgRole.ADMIN: 1, OrgRole.OWNER: 2}
        if org_role_hierarchy.get(membership.role, -1) < org_role_hierarchy.get(min_role, 0):  # type: ignore[call-overload]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {min_role} role in this organization",
            )


async def verify_deal_membership(
    db: AsyncSession,
    user_id: UUID,
    deal_id: UUID,
    min_role: DealRole | None = None,
    required_permission: str | None = None,
) -> None:
    """Verify that a user has access to a deal with the required role/permission.

    Raises HTTPException 403 if the user lacks access.
    """
    from app.models.deal_membership import DealMembership

    stmt = select(DealMembership).where(
        DealMembership.user_id == user_id,
        DealMembership.deal_id == deal_id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    if (
        min_role is not None
        and DEAL_ROLE_HIERARCHY.get(membership.role, -1) < DEAL_ROLE_HIERARCHY.get(min_role, 0)  # type: ignore[call-overload]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_role} role on this deal",
        )

    if required_permission is not None:
        permissions = DEAL_ROLE_PERMISSIONS.get(membership.role, set())  # type: ignore[call-overload]
        if required_permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {required_permission}",
            )
