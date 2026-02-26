from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.models.deal_membership import DealMembership
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.deal import (
    DealCreate,
    DealMemberCreate,
    DealMemberResponse,
    DealResponse,
    DealUpdate,
)
from app.services.deal_service import DealService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[DealResponse])
async def list_deals(
    status: str | None = Query(None, description="Filter by deal status"),
    deal_type: str | None = Query(None, description="Filter by deal type"),
    search: str | None = Query(None, description="Search by name or target company"),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[DealResponse]:
    """List deals the current user has access to."""
    service = DealService(db)
    deals = await service.list_deals(
        org_id=org_id,
        user_id=current_user.id,
        status_filter=status,
        deal_type_filter=deal_type,
        search=search,
    )
    items = [DealResponse.model_validate(d) for d in deals]
    return PaginatedResponse(items=items, cursor=None, has_more=False)


@router.post("/", response_model=DealResponse, status_code=201)
async def create_deal(
    payload: DealCreate,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> DealResponse:
    """Create a new deal. Creator becomes deal lead."""
    service = DealService(db)
    deal = await service.create_deal(
        org_id=org_id,
        creator_id=current_user.id,
        name=payload.name,
        description=payload.description,
        target_company=payload.target_company,
        deal_type=payload.deal_type,
        stage=payload.stage,
    )
    return DealResponse.model_validate(deal)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DealResponse:
    """Get deal details. Requires deal membership."""
    service = DealService(db)
    deal = await service.get_deal(deal_id, current_user.id)
    return DealResponse.model_validate(deal)


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: UUID,
    payload: DealUpdate,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DealResponse:
    """Update deal. Requires deal admin or lead role."""
    service = DealService(db)
    deal = await service.update_deal(
        deal_id=deal_id,
        user_id=current_user.id,
        **payload.model_dump(exclude_unset=True),
    )
    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete deal. Requires deal lead role."""
    service = DealService(db)
    await service.delete_deal(deal_id, current_user.id)


# --- Deal Membership ---


@router.get("/{deal_id}/members", response_model=list[DealMemberResponse])
async def list_deal_members(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> list[DealMemberResponse]:
    """List members of a deal. Requires deal membership."""
    service = DealService(db)
    await service.check_deal_access(deal_id, current_user.id)

    stmt = (
        select(DealMembership)
        .options(joinedload(DealMembership.user))
        .where(DealMembership.deal_id == deal_id)
        .order_by(DealMembership.added_at)
    )
    result = await db.execute(stmt)
    members = result.scalars().unique().all()

    return [
        DealMemberResponse(
            user_id=m.user_id,
            email=m.user.email if m.user else None,
            full_name=m.user.full_name if m.user else None,
            role=m.role,
            added_at=m.added_at,
        )
        for m in members
    ]


@router.post("/{deal_id}/members", response_model=DealMemberResponse, status_code=201)
async def add_deal_member(
    deal_id: UUID,
    payload: DealMemberCreate,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DealMemberResponse:
    """Add a user to the deal. Requires deal admin or lead role."""
    service = DealService(db)
    membership = await service.add_member(
        deal_id=deal_id,
        user_id=payload.user_id,
        role=payload.role,
        added_by=current_user.id,
    )
    return DealMemberResponse(
        user_id=membership.user_id,
        role=membership.role,
        added_at=membership.added_at,
    )


@router.patch("/{deal_id}/members/{user_id}", response_model=DealMemberResponse)
async def update_deal_member_role(
    deal_id: UUID,
    user_id: UUID,
    payload: DealMemberCreate,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DealMemberResponse:
    """Update a deal member's role. Requires deal lead role."""
    service = DealService(db)
    membership = await service.update_member_role(
        deal_id=deal_id,
        user_id=user_id,
        new_role=payload.role,
        updated_by=current_user.id,
    )
    return DealMemberResponse(
        user_id=membership.user_id,
        role=membership.role,
        added_at=membership.added_at,
    )


@router.delete("/{deal_id}/members/{user_id}", status_code=204)
async def remove_deal_member(
    deal_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a member from the deal. Requires deal admin or lead role."""
    service = DealService(db)
    await service.remove_member(
        deal_id=deal_id,
        user_id=user_id,
        removed_by=current_user.id,
    )
