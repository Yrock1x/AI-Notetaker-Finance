"""Deal service — CRUD operations with deal-level RBAC enforcement."""

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import DEAL_ROLE_HIERARCHY, DealRole
from app.models.deal import Deal
from app.models.deal_membership import DealMembership
from app.models.org_membership import OrgMembership

logger = structlog.get_logger(__name__)


class DealService:
    """Service layer for deal management with RBAC enforcement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Deal CRUD
    # ------------------------------------------------------------------

    async def create_deal(
        self,
        org_id: UUID,
        creator_id: UUID,
        name: str,
        description: str | None = None,
        target_company: str | None = None,
        deal_type: str = "general",
        stage: str | None = None,
    ) -> Deal:
        """Create a new deal within an organization and add the creator as lead."""
        deal = Deal(
            org_id=org_id,
            name=name,
            description=description,
            target_company=target_company,
            deal_type=deal_type,
            stage=stage,
            status="active",
            created_by=creator_id,
        )
        self.db.add(deal)
        await self.db.flush()

        # Add creator as deal lead
        membership = DealMembership(
            deal_id=deal.id,
            user_id=creator_id,
            org_id=org_id,
            role=DealRole.LEAD,
            added_by=creator_id,
        )
        self.db.add(membership)
        await self.db.flush()

        logger.info(
            "deal_created",
            deal_id=str(deal.id),
            org_id=str(org_id),
            creator_id=str(creator_id),
            name=name,
        )
        return deal

    async def get_deal(self, deal_id: UUID, user_id: UUID) -> Deal:
        """Get a deal by ID, verifying the user has access.

        Excludes soft-deleted deals.
        Raises NotFoundError if the deal does not exist or is deleted.
        Raises PermissionDeniedError if the user is not a member of the deal.
        """
        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()

        if deal is None:
            raise NotFoundError("Deal", str(deal_id))

        # Verify user has access (any role is sufficient for reading)
        await self.check_deal_access(deal_id, user_id)

        return deal

    async def update_deal(
        self,
        deal_id: UUID,
        user_id: UUID,
        **kwargs: object,
    ) -> Deal:
        """Update deal fields. Requires write permission (analyst or above).

        Accepted kwargs: name, description, target_company, deal_type, stage, status.
        Raises NotFoundError if the deal does not exist.
        Raises PermissionDeniedError if the user lacks write permission.
        """
        # Verify user has at least analyst role (write permission)
        await self.check_deal_access(deal_id, user_id, min_role=DealRole.ANALYST)

        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()

        if deal is None:
            raise NotFoundError("Deal", str(deal_id))

        allowed_fields = {"name", "description", "target_company", "deal_type", "stage", "status"}
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(deal, field, value)

        await self.db.flush()

        logger.info(
            "deal_updated",
            deal_id=str(deal_id),
            user_id=str(user_id),
            updated_fields=list(kwargs.keys()),
        )
        return deal

    async def delete_deal(self, deal_id: UUID, user_id: UUID) -> Deal:
        """Soft-delete a deal by setting deleted_at. Requires lead role.

        Raises NotFoundError if the deal does not exist.
        Raises PermissionDeniedError if the user is not a deal lead.
        """
        await self.check_deal_access(deal_id, user_id, min_role=DealRole.LEAD)

        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()

        if deal is None:
            raise NotFoundError("Deal", str(deal_id))

        deal.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "deal_deleted",
            deal_id=str(deal_id),
            user_id=str(user_id),
        )
        return deal

    async def list_deals(
        self,
        org_id: UUID,
        user_id: UUID,
        status_filter: str | None = None,
        deal_type_filter: str | None = None,
        search: str | None = None,
    ) -> list[Deal]:
        """List deals the user has access to within an org, with optional filters.

        Only returns non-deleted deals that the user is a member of.
        """
        stmt = (
            select(Deal)
            .join(DealMembership, DealMembership.deal_id == Deal.id)
            .where(
                Deal.org_id == org_id,
                Deal.deleted_at.is_(None),
                DealMembership.user_id == user_id,
            )
        )

        if status_filter is not None:
            stmt = stmt.where(Deal.status == status_filter)

        if deal_type_filter is not None:
            stmt = stmt.where(Deal.deal_type == deal_type_filter)

        if search is not None:
            safe_search = search.replace("%", r"\%").replace("_", r"\_")
            search_term = f"%{safe_search}%"
            stmt = stmt.where(
                Deal.name.ilike(search_term) | Deal.target_company.ilike(search_term)
            )

        stmt = stmt.order_by(Deal.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    async def check_deal_access(
        self,
        deal_id: UUID,
        user_id: UUID,
        min_role: DealRole | None = None,
    ) -> DealMembership:
        """Verify a user has access to a deal, optionally at a minimum role level.

        Returns the DealMembership if the user has access.
        Raises PermissionDeniedError if the user is not a member or lacks the
        required role level.
        """
        stmt = select(DealMembership).where(
            DealMembership.deal_id == deal_id,
            DealMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise PermissionDeniedError("You do not have access to this deal")

        if min_role is not None:
            user_level = DEAL_ROLE_HIERARCHY.get(membership.role, -1)
            required_level = DEAL_ROLE_HIERARCHY.get(min_role, 0)
            if user_level < required_level:
                raise PermissionDeniedError(
                    f"Requires at least {min_role} role on this deal"
                )

        return membership

    # ------------------------------------------------------------------
    # Deal membership management
    # ------------------------------------------------------------------

    async def add_member(
        self,
        deal_id: UUID,
        user_id: UUID,
        role: str = DealRole.ANALYST,
        added_by: UUID | None = None,
    ) -> DealMembership:
        """Add a user to a deal.

        Validates that the user belongs to the same org as the deal and that
        they are not already a member.

        Raises NotFoundError if the deal does not exist.
        Raises PermissionDeniedError if the user is not in the deal's org.
        Raises ConflictError if the user is already a deal member.
        """
        # Fetch the deal to get its org_id
        stmt = select(Deal).where(
            Deal.id == deal_id,
            Deal.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        deal = result.scalar_one_or_none()

        if deal is None:
            raise NotFoundError("Deal", str(deal_id))

        # Verify the user being added belongs to the org
        org_membership_stmt = select(OrgMembership).where(
            OrgMembership.org_id == deal.org_id,
            OrgMembership.user_id == user_id,
        )
        result = await self.db.execute(org_membership_stmt)
        org_membership = result.scalar_one_or_none()

        if org_membership is None:
            raise PermissionDeniedError(
                "User must be a member of the organization to join a deal"
            )

        # Check for duplicate deal membership
        existing_stmt = select(DealMembership).where(
            DealMembership.deal_id == deal_id,
            DealMembership.user_id == user_id,
        )
        result = await self.db.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            raise ConflictError("User is already a member of this deal")

        membership = DealMembership(
            deal_id=deal_id,
            user_id=user_id,
            org_id=deal.org_id,
            role=role,
            added_by=added_by,
        )
        self.db.add(membership)
        await self.db.flush()

        logger.info(
            "deal_member_added",
            deal_id=str(deal_id),
            user_id=str(user_id),
            role=role,
            added_by=str(added_by) if added_by else None,
        )
        return membership

    async def remove_member(
        self,
        deal_id: UUID,
        user_id: UUID,
        removed_by: UUID | None = None,
    ) -> None:
        """Remove a user from a deal.

        Cannot remove the last lead of a deal.

        Raises NotFoundError if the membership does not exist.
        Raises PermissionDeniedError if trying to remove the last lead.
        """
        stmt = select(DealMembership).where(
            DealMembership.deal_id == deal_id,
            DealMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise NotFoundError("DealMembership")

        # Prevent removing the last lead
        if membership.role == DealRole.LEAD:
            lead_count_stmt = (
                select(func.count())
                .select_from(DealMembership)
                .where(
                    DealMembership.deal_id == deal_id,
                    DealMembership.role == DealRole.LEAD,
                )
            )
            result = await self.db.execute(lead_count_stmt)
            lead_count = result.scalar_one()

            if lead_count <= 1:
                raise PermissionDeniedError(
                    "Cannot remove the last lead of a deal"
                )

        await self.db.delete(membership)
        await self.db.flush()

        logger.info(
            "deal_member_removed",
            deal_id=str(deal_id),
            user_id=str(user_id),
            removed_by=str(removed_by) if removed_by else None,
        )

    async def update_member_role(
        self,
        deal_id: UUID,
        user_id: UUID,
        new_role: str,
        updated_by: UUID | None = None,
    ) -> DealMembership:
        """Change a member's role on a deal. The updater must be a lead.

        Raises NotFoundError if the membership does not exist.
        Raises PermissionDeniedError if demoting the last lead, or if the
        updater lacks lead role.
        """
        # Verify the person making the change has lead role
        if updated_by is not None:
            await self.check_deal_access(deal_id, updated_by, min_role=DealRole.LEAD)

        stmt = select(DealMembership).where(
            DealMembership.deal_id == deal_id,
            DealMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise NotFoundError("DealMembership")

        # If demoting a lead, make sure they aren't the last one
        if membership.role == DealRole.LEAD and new_role != DealRole.LEAD:
            lead_count_stmt = (
                select(func.count())
                .select_from(DealMembership)
                .where(
                    DealMembership.deal_id == deal_id,
                    DealMembership.role == DealRole.LEAD,
                )
            )
            result = await self.db.execute(lead_count_stmt)
            lead_count = result.scalar_one()

            if lead_count <= 1:
                raise PermissionDeniedError(
                    "Cannot demote the last lead of a deal"
                )

        membership.role = new_role
        await self.db.flush()

        logger.info(
            "deal_member_role_updated",
            deal_id=str(deal_id),
            user_id=str(user_id),
            new_role=new_role,
            updated_by=str(updated_by) if updated_by else None,
        )
        return membership
