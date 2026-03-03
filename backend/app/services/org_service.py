"""Organization service — CRUD operations with RBAC enforcement."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import structlog

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import OrgRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership

logger = structlog.get_logger(__name__)


class OrgService:
    """Service layer for organization management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Organization CRUD
    # ------------------------------------------------------------------

    async def create_org(
        self,
        name: str,
        slug: str,
        domain: str | None = None,
        creator_id: UUID | None = None,
    ) -> Organization:
        """Create a new organization and add the creator as owner.

        Raises ConflictError if the slug is already taken.
        """
        # Check slug uniqueness
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"Organization with slug '{slug}' already exists")

        org = Organization(name=name, slug=slug, domain=domain)
        self.db.add(org)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Organization with this slug already exists")

        logger.info("org_created", org_id=str(org.id), slug=slug)

        # Add creator as owner if provided
        if creator_id is not None:
            membership = OrgMembership(
                org_id=org.id,
                user_id=creator_id,
                role=OrgRole.OWNER,
            )
            self.db.add(membership)
            await self.db.flush()

            logger.info(
                "org_owner_added",
                org_id=str(org.id),
                user_id=str(creator_id),
            )

        return org

    async def get_org(self, org_id: UUID) -> Organization:
        """Get an organization by ID.

        Raises NotFoundError if the organization does not exist.
        """
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self.db.execute(stmt)
        org = result.scalar_one_or_none()

        if org is None:
            raise NotFoundError("Organization", str(org_id))

        return org

    async def update_org(self, org_id: UUID, **kwargs: object) -> Organization:
        """Update organization fields.

        Accepted kwargs: name, domain, settings.
        Raises NotFoundError if the organization does not exist.
        """
        org = await self.get_org(org_id)

        allowed_fields = {"name", "domain", "settings"}
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(org, field, value)

        await self.db.flush()

        logger.info(
            "org_updated",
            org_id=str(org_id),
            updated_fields=list(kwargs.keys()),
        )
        return org

    async def list_user_orgs(self, user_id: UUID) -> list[Organization]:
        """List all organizations a user belongs to via org_memberships."""
        stmt = (
            select(Organization)
            .join(OrgMembership, OrgMembership.org_id == Organization.id)
            .where(OrgMembership.user_id == user_id)
            .order_by(Organization.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Membership management
    # ------------------------------------------------------------------

    async def add_member(
        self,
        org_id: UUID,
        user_id: UUID,
        role: str = OrgRole.MEMBER,
    ) -> OrgMembership:
        """Add a user to an organization.

        Raises ConflictError if the user is already a member.
        Raises NotFoundError if the organization does not exist.
        """
        # Ensure org exists
        await self.get_org(org_id)

        # Check for existing membership
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            raise ConflictError("User is already a member of this organization")

        membership = OrgMembership(
            org_id=org_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(membership)
        await self.db.flush()

        logger.info(
            "org_member_added",
            org_id=str(org_id),
            user_id=str(user_id),
            role=role,
        )
        return membership

    async def remove_member(self, org_id: UUID, user_id: UUID) -> None:
        """Remove a user from an organization.

        Raises NotFoundError if the membership does not exist.
        Raises PermissionDeniedError if trying to remove the last owner.
        """
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise NotFoundError("OrgMembership")

        # Prevent removing the last owner
        if membership.role == OrgRole.OWNER:
            owner_count_stmt = (
                select(func.count())
                .select_from(OrgMembership)
                .where(
                    OrgMembership.org_id == org_id,
                    OrgMembership.role == OrgRole.OWNER,
                )
            )
            result = await self.db.execute(owner_count_stmt)
            owner_count = result.scalar_one()

            if owner_count <= 1:
                raise PermissionDeniedError(
                    "Cannot remove the last owner of an organization"
                )

        await self.db.delete(membership)
        await self.db.flush()

        logger.info(
            "org_member_removed",
            org_id=str(org_id),
            user_id=str(user_id),
        )

    async def update_member_role(
        self,
        org_id: UUID,
        user_id: UUID,
        role: str,
    ) -> OrgMembership:
        """Change a member's role within an organization.

        Raises NotFoundError if the membership does not exist.
        Raises PermissionDeniedError if demoting the last owner.
        """
        stmt = select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership is None:
            raise NotFoundError("OrgMembership")

        # If demoting an owner, make sure they aren't the last one
        if membership.role == OrgRole.OWNER and role != OrgRole.OWNER:
            owner_count_stmt = (
                select(func.count())
                .select_from(OrgMembership)
                .where(
                    OrgMembership.org_id == org_id,
                    OrgMembership.role == OrgRole.OWNER,
                )
            )
            result = await self.db.execute(owner_count_stmt)
            owner_count = result.scalar_one()

            if owner_count <= 1:
                raise PermissionDeniedError(
                    "Cannot demote the last owner of an organization"
                )

        membership.role = role
        await self.db.flush()

        logger.info(
            "org_member_role_updated",
            org_id=str(org_id),
            user_id=str(user_id),
            new_role=role,
        )
        return membership

    async def list_members(self, org_id: UUID) -> list[OrgMembership]:
        """List all members of an organization with their user info.

        Returns OrgMembership objects with the `user` relationship loaded.
        Raises NotFoundError if the organization does not exist.
        """
        # Ensure org exists
        await self.get_org(org_id)

        stmt = (
            select(OrgMembership)
            .options(joinedload(OrgMembership.user))
            .where(OrgMembership.org_id == org_id)
            .order_by(OrgMembership.joined_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())
