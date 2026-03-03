"""Unit tests for DealService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import DealRole
from app.models.deal import Deal
from app.models.deal_membership import DealMembership
from app.models.org_membership import OrgMembership
from app.services.deal_service import DealService


def _make_deal(org_id=None, created_by=None, **kwargs):
    deal = MagicMock(spec=Deal)
    deal.id = kwargs.get("id", uuid.uuid4())
    deal.org_id = org_id or uuid.uuid4()
    deal.name = kwargs.get("name", "Test Deal")
    deal.status = kwargs.get("status", "active")
    deal.deal_type = kwargs.get("deal_type", "m_and_a")
    deal.created_by = created_by or uuid.uuid4()
    deal.deleted_at = kwargs.get("deleted_at")
    deal.created_at = datetime.now(UTC)
    return deal


def _make_membership(deal_id=None, user_id=None, role=DealRole.ANALYST, **kwargs):
    m = MagicMock(spec=DealMembership)
    m.deal_id = deal_id or uuid.uuid4()
    m.user_id = user_id or uuid.uuid4()
    m.role = role
    m.org_id = kwargs.get("org_id", uuid.uuid4())
    return m


def _mock_scalar_result(value):
    """Create a mock result object that returns value from scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalar_one(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_create_deal_returns_deal(self):
        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        service = DealService(db)

        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        deal = await service.create_deal(org_id=org_id, creator_id=user_id, name="Alpha")

        assert deal.name == "Alpha"
        assert deal.org_id == org_id
        assert deal.status == "active"

    @pytest.mark.asyncio
    async def test_create_deal_adds_creator_as_lead(self):
        db = AsyncMock()
        db.flush = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        service = DealService(db)

        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await service.create_deal(org_id=org_id, creator_id=user_id, name="Alpha")

        # Should have added a Deal and a DealMembership
        memberships = [o for o in added_objects if isinstance(o, DealMembership)]
        assert len(memberships) == 1
        assert memberships[0].role == DealRole.LEAD
        assert memberships[0].user_id == user_id


class TestGetDeal:
    @pytest.mark.asyncio
    async def test_get_deal_not_found_raises(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(None))
        service = DealService(db)

        with pytest.raises(NotFoundError):
            await service.get_deal(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_deal_no_membership_raises(self):
        deal = _make_deal()
        db = AsyncMock()
        # First call returns the deal, second call returns None (no membership)
        db.execute = AsyncMock(side_effect=[
            _mock_scalar_result(deal),
            _mock_scalar_result(None),
        ])
        service = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await service.get_deal(deal.id, uuid.uuid4())


class TestDeleteDeal:
    @pytest.mark.asyncio
    async def test_delete_deal_sets_deleted_at(self):
        deal = _make_deal()
        deal.deleted_at = None
        membership = _make_membership(deal_id=deal.id, role=DealRole.LEAD)

        db = AsyncMock()
        db.flush = AsyncMock()
        # check_deal_access returns membership, then get deal returns deal
        db.execute = AsyncMock(side_effect=[
            _mock_scalar_result(membership),  # check_deal_access
            _mock_scalar_result(deal),  # select deal in delete_deal
        ])
        service = DealService(db)

        result = await service.delete_deal(deal.id, membership.user_id)
        assert result.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_deal_requires_lead(self):
        membership = _make_membership(role=DealRole.ANALYST)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(membership))
        service = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await service.delete_deal(uuid.uuid4(), membership.user_id)


class TestAddMember:
    @pytest.mark.asyncio
    async def test_add_member_duplicate_raises_conflict(self):
        deal = _make_deal()
        existing = _make_membership(deal_id=deal.id)
        org_membership = MagicMock(spec=OrgMembership)

        db = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _mock_scalar_result(deal),        # get deal
            _mock_scalar_result(org_membership),  # org membership check
            _mock_scalar_result(existing),    # existing deal membership
        ])
        service = DealService(db)

        with pytest.raises(ConflictError):
            await service.add_member(deal.id, existing.user_id, DealRole.ANALYST)

    @pytest.mark.asyncio
    async def test_add_member_not_in_org_raises(self):
        deal = _make_deal()

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _mock_scalar_result(deal),  # get deal
            _mock_scalar_result(None),  # no org membership
        ])
        service = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await service.add_member(deal.id, uuid.uuid4(), DealRole.ANALYST)


class TestRemoveMember:
    @pytest.mark.asyncio
    async def test_remove_last_lead_raises(self):
        membership = _make_membership(role=DealRole.LEAD)

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _mock_scalar_result(membership),  # find membership
            _mock_scalar_one(1),  # lead count = 1
        ])
        service = DealService(db)

        with pytest.raises(PermissionDeniedError, match="last lead"):
            await service.remove_member(uuid.uuid4(), membership.user_id)

    @pytest.mark.asyncio
    async def test_remove_nonexistent_raises_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(None))
        service = DealService(db)

        with pytest.raises(NotFoundError):
            await service.remove_member(uuid.uuid4(), uuid.uuid4())
