from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import OrgRole, verify_org_membership
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserResponse
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.org_service import OrgService

router = APIRouter()


# --- Users ---


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    search: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> PaginatedResponse[UserResponse]:
    """List all users in the organization. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)

    # Get all org members with user info
    stmt = (
        select(OrgMembership)
        .options(joinedload(OrgMembership.user))
        .where(OrgMembership.org_id == org_id)
        .order_by(OrgMembership.joined_at.desc())
    )

    if search:
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        stmt = stmt.join(User, OrgMembership.user_id == User.id).where(
            User.email.ilike(f"%{safe_search}%") | User.full_name.ilike(f"%{safe_search}%")
        )

    if cursor:
        from datetime import datetime
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(OrgMembership.joined_at < cursor_dt)
        except ValueError:
            pass

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    memberships = list(result.scalars().unique().all())

    has_more = len(memberships) > limit
    if has_more:
        memberships = memberships[:limit]

    items = [UserResponse.model_validate(m.user) for m in memberships]
    next_cursor = None
    if has_more and memberships:
        next_cursor = memberships[-1].joined_at.isoformat()

    return PaginatedResponse(items=items, cursor=next_cursor, has_more=has_more)


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> UserResponse:
    """Deactivate a user in the organization. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    from app.integrations.aws.cognito import get_cognito_client

    auth_service = AuthService(db=db, cognito=get_cognito_client())
    user = await auth_service.deactivate_user(user_id)
    return UserResponse.model_validate(user)


# --- Audit Logs ---


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogResponse])
async def query_audit_logs(
    user_id: UUID | None = Query(None),
    deal_id: UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> PaginatedResponse[AuditLogResponse]:
    """Query audit logs. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)

    audit_service = AuditService(db)
    result = await audit_service.query_logs(
        org_id=org_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        deal_id=deal_id,
        cursor=cursor,
        limit=limit,
    )
    items = [AuditLogResponse.model_validate(log) for log in result["items"]]
    return PaginatedResponse(
        items=items,
        cursor=result["cursor"],
        has_more=result["has_more"],
    )


# --- Org Settings ---


@router.get("/settings")
async def get_org_settings(
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> dict:
    """Get organization settings. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)

    service = OrgService(db)
    org = await service.get_org(org_id)
    return org.settings or {}


@router.patch("/settings")
async def update_org_settings(
    settings: dict,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> dict:
    """Update organization settings. Requires admin role."""
    await verify_org_membership(db, current_user.id, org_id, min_role=OrgRole.ADMIN)

    service = OrgService(db)
    org = await service.update_org(org_id, settings=settings)
    return org.settings or {}
