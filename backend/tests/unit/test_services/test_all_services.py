"""Comprehensive unit tests for all service layer classes.

Covers:
- Service instantiation with mock dependencies
- Method contracts (correct exception types, return types)
- Business logic: RBAC checks, duplicate guards, last-owner/lead protections
- Implemented behavior in deal_service, auth_service, org_service,
  meeting_service, document_service, analysis_service, qa_service, audit_service

All database sessions and external clients are mocked.
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import DEAL_ROLE_HIERARCHY, DealRole, OrgRole
from app.models.analysis import Analysis
from app.models.audit_log import AuditLog

# ── Model imports (used for MagicMock specs) ─────────────────────────────────
from app.models.deal import Deal
from app.models.deal_membership import DealMembership
from app.models.document import Document
from app.models.meeting import Meeting
from app.models.meeting_participant import MeetingParticipant
from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.user import User
from app.services.analysis_service import AnalysisService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

# ── Service imports ──────────────────────────────────────────────────────────
from app.services.deal_service import DealService
from app.services.document_service import DocumentService
from app.services.meeting_service import MeetingService
from app.services.org_service import OrgService
from app.services.qa_service import Citation, QAResponse, QAService

# ═══════════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _scalar_result(value):
    """Create a mock result whose scalar_one_or_none() returns *value*."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalar_one_result(value):
    """Create a mock result whose scalar_one() returns *value*."""
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _scalars_all_result(values):
    """Create a mock result whose scalars().all() returns *values*."""
    r = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    scalars_mock.unique.return_value = scalars_mock
    r.scalars.return_value = scalars_mock
    return r


def _mock_db():
    """Return a fresh AsyncMock for an AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_deal(**kw):
    m = MagicMock(spec=Deal)
    m.id = kw.get("id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.name = kw.get("name", "Test Deal")
    m.status = kw.get("status", "active")
    m.deal_type = kw.get("deal_type", "m_and_a")
    m.created_by = kw.get("created_by", uuid.uuid4())
    m.deleted_at = kw.get("deleted_at")
    m.created_at = datetime.now(UTC)
    return m


def _make_membership(role=DealRole.ANALYST, **kw):
    m = MagicMock(spec=DealMembership)
    m.deal_id = kw.get("deal_id", uuid.uuid4())
    m.user_id = kw.get("user_id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.role = role
    return m


def _make_org_membership(role=OrgRole.MEMBER, **kw):
    m = MagicMock(spec=OrgMembership)
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.user_id = kw.get("user_id", uuid.uuid4())
    m.role = role
    return m


def _make_org(**kw):
    m = MagicMock(spec=Organization)
    m.id = kw.get("id", uuid.uuid4())
    m.name = kw.get("name", "Test Org")
    m.slug = kw.get("slug", "test-org")
    m.domain = kw.get("domain")
    return m


def _make_user(**kw):
    m = MagicMock(spec=User)
    m.id = kw.get("id", uuid.uuid4())
    m.cognito_sub = kw.get("cognito_sub", f"cognito-{uuid.uuid4()}")
    m.email = kw.get("email", "user@example.com")
    m.full_name = kw.get("full_name", "Test User")
    m.is_active = kw.get("is_active", True)
    return m


def _make_meeting(**kw):
    m = MagicMock(spec=Meeting)
    m.id = kw.get("id", uuid.uuid4())
    m.deal_id = kw.get("deal_id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.title = kw.get("title", "Test Meeting")
    m.status = kw.get("status", "uploading")
    m.file_key = kw.get("file_key", "orgs/x/deals/y/meetings/z/audio.mp3")
    m.created_at = datetime.now(UTC)
    m.created_by = kw.get("created_by", uuid.uuid4())
    return m


def _make_document(**kw):
    m = MagicMock(spec=Document)
    m.id = kw.get("id", uuid.uuid4())
    m.deal_id = kw.get("deal_id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.title = kw.get("title", "report.pdf")
    m.document_type = kw.get("document_type", "pdf")
    m.file_key = kw.get("file_key", "orgs/x/deals/y/documents/z/report.pdf")
    m.file_size = kw.get("file_size", 1024)
    m.extracted_text = kw.get("extracted_text")
    m.created_at = datetime.now(UTC)
    return m


def _make_analysis(**kw):
    m = MagicMock(spec=Analysis)
    m.id = kw.get("id", uuid.uuid4())
    m.meeting_id = kw.get("meeting_id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.call_type = kw.get("call_type", "diligence")
    m.status = kw.get("status", "completed")
    m.version = kw.get("version", 1)
    m.model_used = kw.get("model_used", "claude-3-opus")
    m.prompt_version = kw.get("prompt_version", "v1")
    m.structured_output = kw.get("structured_output", {"key": "value"})
    m.requested_by = kw.get("requested_by", uuid.uuid4())
    m.error_message = kw.get("error_message")
    m.created_at = datetime.now(UTC)
    return m


def _make_audit_log(**kw):
    m = MagicMock(spec=AuditLog)
    m.id = kw.get("id", uuid.uuid4())
    m.org_id = kw.get("org_id", uuid.uuid4())
    m.user_id = kw.get("user_id", uuid.uuid4())
    m.action = kw.get("action", "create")
    m.resource_type = kw.get("resource_type", "deal")
    m.resource_id = kw.get("resource_id", uuid.uuid4())
    m.created_at = kw.get("created_at", datetime.now(UTC))
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — instantiation
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceInstantiation:
    def test_instantiation_stores_db(self):
        db = _mock_db()
        svc = DealService(db)
        assert svc.db is db


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — create_deal
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceCreateDeal:
    @pytest.mark.asyncio
    async def test_create_deal_returns_deal_with_correct_fields(self):
        db = _mock_db()
        svc = DealService(db)
        org_id, user_id = uuid.uuid4(), uuid.uuid4()

        deal = await svc.create_deal(
            org_id=org_id, creator_id=user_id, name="Alpha",
            deal_type="m_and_a", stage="screening",
        )

        assert deal.name == "Alpha"
        assert deal.org_id == org_id
        assert deal.created_by == user_id
        assert deal.status == "active"
        assert deal.deal_type == "m_and_a"
        assert deal.stage == "screening"

    @pytest.mark.asyncio
    async def test_create_deal_adds_creator_as_lead(self):
        db = _mock_db()
        added = []
        db.add = lambda obj: added.append(obj)
        svc = DealService(db)

        await svc.create_deal(
            org_id=uuid.uuid4(), creator_id=uuid.uuid4(), name="Beta",
        )

        memberships = [o for o in added if isinstance(o, DealMembership)]
        assert len(memberships) == 1
        assert memberships[0].role == DealRole.LEAD

    @pytest.mark.asyncio
    async def test_create_deal_flushes_twice(self):
        db = _mock_db()
        svc = DealService(db)
        await svc.create_deal(
            org_id=uuid.uuid4(), creator_id=uuid.uuid4(), name="Gamma",
        )
        assert db.flush.await_count == 2  # once for deal, once for membership


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — get_deal
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceGetDeal:
    @pytest.mark.asyncio
    async def test_get_deal_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = DealService(db)

        with pytest.raises(NotFoundError):
            await svc.get_deal(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_deal_no_membership_raises_permission(self):
        deal = _make_deal()
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(deal),    # deal found
            _scalar_result(None),    # no membership
        ])
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await svc.get_deal(deal.id, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_deal_success_returns_deal(self):
        deal = _make_deal()
        membership = _make_membership(deal_id=deal.id, role=DealRole.VIEWER)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(deal),
            _scalar_result(membership),
        ])
        svc = DealService(db)

        result = await svc.get_deal(deal.id, membership.user_id)
        assert result is deal


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — update_deal
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceUpdateDeal:
    @pytest.mark.asyncio
    async def test_update_deal_requires_analyst_role(self):
        membership = _make_membership(role=DealRole.VIEWER)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await svc.update_deal(uuid.uuid4(), membership.user_id, name="X")

    @pytest.mark.asyncio
    async def test_update_deal_sets_allowed_fields(self):
        deal = _make_deal()
        membership = _make_membership(deal_id=deal.id, role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),  # check_deal_access
            _scalar_result(deal),        # select deal
        ])
        svc = DealService(db)

        result = await svc.update_deal(
            deal.id, membership.user_id, name="Updated", status="closed",
        )
        assert result.name == "Updated"
        assert result.status == "closed"

    @pytest.mark.asyncio
    async def test_update_deal_ignores_disallowed_fields(self):
        deal = _make_deal()
        original_id = deal.id
        membership = _make_membership(deal_id=deal.id, role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_result(deal),
        ])
        svc = DealService(db)

        await svc.update_deal(deal.id, membership.user_id, id=uuid.uuid4())
        # id should not have changed since it's not in allowed_fields
        assert deal.id == original_id

    @pytest.mark.asyncio
    async def test_update_deal_not_found_after_access_check_raises(self):
        membership = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),  # check_deal_access passes
            _scalar_result(None),        # deal not found (soft-deleted?)
        ])
        svc = DealService(db)

        with pytest.raises(NotFoundError):
            await svc.update_deal(uuid.uuid4(), membership.user_id, name="X")


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — delete_deal
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceDeleteDeal:
    @pytest.mark.asyncio
    async def test_delete_deal_requires_lead(self):
        membership = _make_membership(role=DealRole.ADMIN)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await svc.delete_deal(uuid.uuid4(), membership.user_id)

    @pytest.mark.asyncio
    async def test_delete_deal_sets_deleted_at(self):
        deal = _make_deal()
        deal.deleted_at = None
        membership = _make_membership(deal_id=deal.id, role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_result(deal),
        ])
        svc = DealService(db)

        result = await svc.delete_deal(deal.id, membership.user_id)
        assert result.deleted_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — list_deals
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceListDeals:
    @pytest.mark.asyncio
    async def test_list_deals_returns_list(self):
        deals = [_make_deal(), _make_deal()]
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result(deals))
        svc = DealService(db)

        result = await svc.list_deals(uuid.uuid4(), uuid.uuid4())
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_deals_empty_when_no_membership(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result([]))
        svc = DealService(db)

        result = await svc.list_deals(uuid.uuid4(), uuid.uuid4())
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — check_deal_access (RBAC)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceCheckDealAccess:
    @pytest.mark.asyncio
    async def test_no_membership_raises_permission_denied(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError, match="do not have access"):
            await svc.check_deal_access(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_any_role_sufficient_when_no_min_role(self):
        membership = _make_membership(role=DealRole.VIEWER)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        result = await svc.check_deal_access(membership.deal_id, membership.user_id)
        assert result is membership

    @pytest.mark.asyncio
    async def test_viewer_cannot_access_analyst_min_role(self):
        membership = _make_membership(role=DealRole.VIEWER)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError, match="analyst"):
            await svc.check_deal_access(
                membership.deal_id, membership.user_id, min_role=DealRole.ANALYST,
            )

    @pytest.mark.asyncio
    async def test_lead_can_access_any_min_role(self):
        membership = _make_membership(role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        for role in [DealRole.VIEWER, DealRole.ANALYST, DealRole.ADMIN, DealRole.LEAD]:
            result = await svc.check_deal_access(
                membership.deal_id, membership.user_id, min_role=role,
            )
            assert result is membership

    @pytest.mark.asyncio
    async def test_analyst_can_access_analyst_min_role(self):
        membership = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        result = await svc.check_deal_access(
            membership.deal_id, membership.user_id, min_role=DealRole.ANALYST,
        )
        assert result is membership

    @pytest.mark.asyncio
    async def test_analyst_cannot_access_admin_min_role(self):
        membership = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError):
            await svc.check_deal_access(
                membership.deal_id, membership.user_id, min_role=DealRole.ADMIN,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — add_member
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceAddMember:
    @pytest.mark.asyncio
    async def test_add_member_deal_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = DealService(db)

        with pytest.raises(NotFoundError):
            await svc.add_member(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_add_member_not_in_org_raises_permission_denied(self):
        deal = _make_deal()
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(deal),   # deal found
            _scalar_result(None),   # no org membership
        ])
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError, match="member of the organization"):
            await svc.add_member(deal.id, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_add_member_duplicate_raises_conflict(self):
        deal = _make_deal()
        org_mem = _make_org_membership(org_id=deal.org_id)
        existing = _make_membership(deal_id=deal.id)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(deal),
            _scalar_result(org_mem),
            _scalar_result(existing),
        ])
        svc = DealService(db)

        with pytest.raises(ConflictError, match="already a member"):
            await svc.add_member(deal.id, existing.user_id)

    @pytest.mark.asyncio
    async def test_add_member_success(self):
        deal = _make_deal()
        org_mem = _make_org_membership(org_id=deal.org_id)
        user_id = uuid.uuid4()
        db = _mock_db()
        added = []
        db.add = lambda obj: added.append(obj)
        db.execute = AsyncMock(side_effect=[
            _scalar_result(deal),
            _scalar_result(org_mem),
            _scalar_result(None),  # no existing membership
        ])
        svc = DealService(db)

        result = await svc.add_member(deal.id, user_id, role=DealRole.ANALYST)
        assert isinstance(result, DealMembership)
        assert result.role == DealRole.ANALYST


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — remove_member
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceRemoveMember:
    @pytest.mark.asyncio
    async def test_remove_nonexistent_raises_not_found(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = DealService(db)

        with pytest.raises(NotFoundError):
            await svc.remove_member(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_remove_last_lead_raises_permission_denied(self):
        membership = _make_membership(role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_one_result(1),  # only 1 lead
        ])
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError, match="last lead"):
            await svc.remove_member(membership.deal_id, membership.user_id)

    @pytest.mark.asyncio
    async def test_remove_lead_with_multiple_leads_succeeds(self):
        membership = _make_membership(role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_one_result(2),  # 2 leads
        ])
        svc = DealService(db)

        await svc.remove_member(membership.deal_id, membership.user_id)
        db.delete.assert_awaited_once_with(membership)

    @pytest.mark.asyncio
    async def test_remove_non_lead_member_succeeds(self):
        membership = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = DealService(db)

        await svc.remove_member(membership.deal_id, membership.user_id)
        db.delete.assert_awaited_once_with(membership)


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — update_member_role
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealServiceUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_demote_last_lead_raises(self):
        # updater is a lead
        updater_mem = _make_membership(role=DealRole.LEAD)
        # target is also a lead
        target_mem = _make_membership(role=DealRole.LEAD)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(updater_mem),   # check updater is lead
            _scalar_result(target_mem),    # find target membership
            _scalar_one_result(1),         # only 1 lead
        ])
        svc = DealService(db)

        with pytest.raises(PermissionDeniedError, match="last lead"):
            await svc.update_member_role(
                target_mem.deal_id, target_mem.user_id,
                DealRole.ANALYST, updated_by=updater_mem.user_id,
            )

    @pytest.mark.asyncio
    async def test_update_role_success(self):
        updater_mem = _make_membership(role=DealRole.LEAD)
        target_mem = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(updater_mem),
            _scalar_result(target_mem),
        ])
        svc = DealService(db)

        result = await svc.update_member_role(
            target_mem.deal_id, target_mem.user_id,
            DealRole.ADMIN, updated_by=updater_mem.user_id,
        )
        assert result.role == DealRole.ADMIN

    @pytest.mark.asyncio
    async def test_update_role_without_updater_skips_access_check(self):
        target_mem = _make_membership(role=DealRole.ANALYST)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(target_mem))
        svc = DealService(db)

        result = await svc.update_member_role(
            target_mem.deal_id, target_mem.user_id, DealRole.VIEWER,
            updated_by=None,
        )
        assert result.role == DealRole.VIEWER
        # Only 1 execute call (no access check)
        assert db.execute.await_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# DealService — RBAC hierarchy correctness
# ═══════════════════════════════════════════════════════════════════════════════

class TestDealRoleHierarchy:
    def test_hierarchy_ordering(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.VIEWER] < DEAL_ROLE_HIERARCHY[DealRole.ANALYST]
        assert DEAL_ROLE_HIERARCHY[DealRole.ANALYST] < DEAL_ROLE_HIERARCHY[DealRole.ADMIN]
        assert DEAL_ROLE_HIERARCHY[DealRole.ADMIN] < DEAL_ROLE_HIERARCHY[DealRole.LEAD]

    def test_lead_is_highest(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.LEAD] == max(DEAL_ROLE_HIERARCHY.values())

    def test_viewer_is_lowest(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.VIEWER] == min(DEAL_ROLE_HIERARCHY.values())


# ═══════════════════════════════════════════════════════════════════════════════
# AuthService
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceInstantiation:
    def test_stores_db_and_cognito(self):
        db = _mock_db()
        cognito = MagicMock()
        svc = AuthService(db, cognito)
        assert svc.db is db
        assert svc.cognito is cognito


class TestAuthServiceVerifyAndGetUser:
    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_jwt_error(self):
        from jose import JWTError

        db = _mock_db()
        cognito = AsyncMock()
        cognito.verify_token = AsyncMock(return_value={"email": "a@b.com"})  # no 'sub'
        svc = AuthService(db, cognito)

        with pytest.raises(JWTError, match="sub"):
            await svc.verify_and_get_user("fake-token")

    @pytest.mark.asyncio
    async def test_verify_returns_existing_user(self):
        user = _make_user()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        cognito = AsyncMock()
        cognito.verify_token = AsyncMock(return_value={
            "sub": user.cognito_sub,
            "email": user.email,
            "name": user.full_name,
        })
        svc = AuthService(db, cognito)

        result = await svc.verify_and_get_user("token")
        assert result is user

    @pytest.mark.asyncio
    async def test_verify_creates_new_user_on_first_login(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        cognito = AsyncMock()
        cognito.verify_token = AsyncMock(return_value={
            "sub": "new-sub",
            "email": "new@example.com",
            "name": "New User",
        })
        svc = AuthService(db, cognito)

        result = await svc.verify_and_get_user("token")
        assert isinstance(result, User)
        assert result.is_active is False  # Pending org assignment
        db.add.assert_called_once()


class TestAuthServiceGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_updates_email_if_changed(self):
        user = _make_user(email="old@example.com")
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        cognito = AsyncMock()
        svc = AuthService(db, cognito)

        result = await svc.get_or_create_user(user.cognito_sub, "new@example.com", user.full_name)
        assert result.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_updates_name_if_changed(self):
        user = _make_user(full_name="Old Name")
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        cognito = AsyncMock()
        svc = AuthService(db, cognito)

        result = await svc.get_or_create_user(user.cognito_sub, user.email, "New Name")
        assert result.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_no_update_when_unchanged(self):
        user = _make_user()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        cognito = AsyncMock()
        svc = AuthService(db, cognito)

        await svc.get_or_create_user(user.cognito_sub, user.email, user.full_name)
        db.flush.assert_not_awaited()  # No changes, no flush


class TestAuthServiceGetUserById:
    @pytest.mark.asyncio
    async def test_get_user_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = AuthService(db, MagicMock())

        with pytest.raises(NotFoundError):
            await svc.get_user_by_id(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_user_success(self):
        user = _make_user()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        svc = AuthService(db, MagicMock())

        result = await svc.get_user_by_id(user.id)
        assert result is user


class TestAuthServiceGetUserByEmail:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = AuthService(db, MagicMock())

        result = await svc.get_user_by_email("nonexistent@example.com")
        assert result is None


class TestAuthServiceDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivate_sets_is_active_false(self):
        user = _make_user(is_active=True)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(user))
        svc = AuthService(db, MagicMock())

        result = await svc.deactivate_user(user.id)
        assert result.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# OrgService
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrgServiceInstantiation:
    def test_stores_db(self):
        db = _mock_db()
        svc = OrgService(db)
        assert svc.db is db


class TestOrgServiceCreateOrg:
    @pytest.mark.asyncio
    async def test_create_org_success(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))  # no slug conflict
        added = []
        db.add = lambda obj: added.append(obj)
        svc = OrgService(db)

        result = await svc.create_org("My Org", "my-org", creator_id=uuid.uuid4())
        assert isinstance(result, Organization)
        assert result.name == "My Org"
        # creator should be added as owner
        memberships = [o for o in added if isinstance(o, OrgMembership)]
        assert len(memberships) == 1
        assert memberships[0].role == OrgRole.OWNER

    @pytest.mark.asyncio
    async def test_create_org_duplicate_slug_raises_conflict(self):
        existing = _make_org(slug="taken")
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(existing))
        svc = OrgService(db)

        with pytest.raises(ConflictError, match="slug"):
            await svc.create_org("New Org", "taken")

    @pytest.mark.asyncio
    async def test_create_org_without_creator_skips_membership(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        added = []
        db.add = lambda obj: added.append(obj)
        svc = OrgService(db)

        await svc.create_org("Solo Org", "solo-org")
        memberships = [o for o in added if isinstance(o, OrgMembership)]
        assert len(memberships) == 0


class TestOrgServiceGetOrg:
    @pytest.mark.asyncio
    async def test_get_org_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.get_org(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_org_success(self):
        org = _make_org()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(org))
        svc = OrgService(db)

        result = await svc.get_org(org.id)
        assert result is org


class TestOrgServiceUpdateOrg:
    @pytest.mark.asyncio
    async def test_update_org_sets_allowed_fields(self):
        org = _make_org()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(org))
        svc = OrgService(db)

        result = await svc.update_org(org.id, name="Updated Org")
        assert result.name == "Updated Org"

    @pytest.mark.asyncio
    async def test_update_org_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.update_org(uuid.uuid4(), name="X")


class TestOrgServiceListUserOrgs:
    @pytest.mark.asyncio
    async def test_list_user_orgs_returns_list(self):
        orgs = [_make_org(), _make_org()]
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result(orgs))
        svc = OrgService(db)

        result = await svc.list_user_orgs(uuid.uuid4())
        assert len(result) == 2


class TestOrgServiceAddMember:
    @pytest.mark.asyncio
    async def test_add_member_org_not_found_raises(self):
        db = _mock_db()
        # get_org will fail
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.add_member(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_add_member_duplicate_raises_conflict(self):
        org = _make_org()
        existing = _make_org_membership(org_id=org.id)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(org),       # get_org
            _scalar_result(existing),  # existing membership
        ])
        svc = OrgService(db)

        with pytest.raises(ConflictError, match="already a member"):
            await svc.add_member(org.id, existing.user_id)

    @pytest.mark.asyncio
    async def test_add_member_success(self):
        org = _make_org()
        db = _mock_db()
        added = []
        db.add = lambda obj: added.append(obj)
        db.execute = AsyncMock(side_effect=[
            _scalar_result(org),   # get_org
            _scalar_result(None),  # no existing membership
        ])
        svc = OrgService(db)

        result = await svc.add_member(org.id, uuid.uuid4(), role=OrgRole.MEMBER)
        assert isinstance(result, OrgMembership)
        assert result.role == OrgRole.MEMBER


class TestOrgServiceRemoveMember:
    @pytest.mark.asyncio
    async def test_remove_nonexistent_raises_not_found(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.remove_member(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_remove_last_owner_raises_permission_denied(self):
        membership = _make_org_membership(role=OrgRole.OWNER)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_one_result(1),  # only 1 owner
        ])
        svc = OrgService(db)

        with pytest.raises(PermissionDeniedError, match="last owner"):
            await svc.remove_member(membership.org_id, membership.user_id)

    @pytest.mark.asyncio
    async def test_remove_owner_with_multiple_owners_succeeds(self):
        membership = _make_org_membership(role=OrgRole.OWNER)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_one_result(2),
        ])
        svc = OrgService(db)

        await svc.remove_member(membership.org_id, membership.user_id)
        db.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_regular_member_succeeds(self):
        membership = _make_org_membership(role=OrgRole.MEMBER)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = OrgService(db)

        await svc.remove_member(membership.org_id, membership.user_id)
        db.delete.assert_awaited_once()


class TestOrgServiceUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_demote_last_owner_raises(self):
        membership = _make_org_membership(role=OrgRole.OWNER)
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            _scalar_result(membership),
            _scalar_one_result(1),
        ])
        svc = OrgService(db)

        with pytest.raises(PermissionDeniedError, match="last owner"):
            await svc.update_member_role(
                membership.org_id, membership.user_id, OrgRole.MEMBER,
            )

    @pytest.mark.asyncio
    async def test_update_role_success(self):
        membership = _make_org_membership(role=OrgRole.MEMBER)
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(membership))
        svc = OrgService(db)

        result = await svc.update_member_role(
            membership.org_id, membership.user_id, OrgRole.ADMIN,
        )
        assert result.role == OrgRole.ADMIN

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises_not_found(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.update_member_role(uuid.uuid4(), uuid.uuid4(), OrgRole.ADMIN)


class TestOrgServiceListMembers:
    @pytest.mark.asyncio
    async def test_list_members_org_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = OrgService(db)

        with pytest.raises(NotFoundError):
            await svc.list_members(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════════════
# MeetingService
# ═══════════════════════════════════════════════════════════════════════════════

class TestMeetingServiceInstantiation:
    def test_stores_deps(self):
        db = _mock_db()
        s3 = MagicMock()
        settings = MagicMock()
        svc = MeetingService(db, s3, settings)
        assert svc.db is db
        assert svc.s3_client is s3
        assert svc.settings is settings


class TestMeetingServiceS3Key:
    def test_s3_key_format(self):
        svc = MeetingService(_mock_db(), MagicMock(), MagicMock())
        org_id = uuid.uuid4()
        deal_id = uuid.uuid4()
        key = svc._s3_key(org_id, deal_id, "audio.mp3")
        assert key.startswith(f"orgs/{org_id}/deals/{deal_id}/meetings/")
        assert key.endswith("/audio.mp3")

    def test_s3_key_is_unique(self):
        svc = MeetingService(_mock_db(), MagicMock(), MagicMock())
        org_id, deal_id = uuid.uuid4(), uuid.uuid4()
        k1 = svc._s3_key(org_id, deal_id, "audio.mp3")
        k2 = svc._s3_key(org_id, deal_id, "audio.mp3")
        assert k1 != k2  # uuid4 segment ensures uniqueness


class TestMeetingServiceCreateMeeting:
    @pytest.mark.asyncio
    async def test_create_meeting_from_upload(self):
        db = _mock_db()
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.create_meeting_from_upload(
            deal_id=uuid.uuid4(), org_id=uuid.uuid4(),
            title="Q1 Call", uploaded_by=uuid.uuid4(),
            s3_key="orgs/x/deals/y/meetings/z/audio.mp3",
        )
        assert isinstance(result, Meeting)
        assert result.title == "Q1 Call"
        assert result.status == "uploading"
        assert result.source == "upload"
        db.add.assert_called_once()


class TestMeetingServiceGetMeeting:
    @pytest.mark.asyncio
    async def test_get_meeting_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = MeetingService(db, MagicMock(), MagicMock())

        with pytest.raises(NotFoundError):
            await svc.get_meeting(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_meeting_success(self):
        meeting = _make_meeting()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(meeting))
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.get_meeting(meeting.id)
        assert result is meeting


class TestMeetingServiceUpdateStatus:
    @pytest.mark.asyncio
    async def test_update_status(self):
        meeting = _make_meeting(status="uploading")
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(meeting))
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.update_meeting_status(meeting.id, "transcribing")
        assert result.status == "transcribing"

    @pytest.mark.asyncio
    async def test_update_status_with_error_message(self):
        meeting = _make_meeting()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(meeting))
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.update_meeting_status(meeting.id, "failed", error_message="Timeout")
        assert result.status == "failed"
        assert result.error_message == "Timeout"


class TestMeetingServiceDeleteMeeting:
    @pytest.mark.asyncio
    async def test_delete_meeting_deletes_s3_and_db(self):
        meeting = _make_meeting()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(meeting))
        s3 = AsyncMock()
        svc = MeetingService(db, s3, MagicMock())

        await svc.delete_meeting(meeting.id)
        s3.delete_file.assert_awaited_once_with(meeting.file_key)
        db.delete.assert_awaited_once_with(meeting)

    @pytest.mark.asyncio
    async def test_delete_meeting_s3_failure_does_not_block(self):
        meeting = _make_meeting()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(meeting))
        s3 = AsyncMock()
        s3.delete_file = AsyncMock(side_effect=Exception("S3 down"))
        svc = MeetingService(db, s3, MagicMock())

        await svc.delete_meeting(meeting.id)  # should not raise
        db.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = MeetingService(db, MagicMock(), MagicMock())

        with pytest.raises(NotFoundError):
            await svc.delete_meeting(uuid.uuid4())


class TestMeetingServiceAddParticipants:
    @pytest.mark.asyncio
    async def test_add_participants(self):
        db = _mock_db()
        added = []
        db.add = lambda obj: added.append(obj)
        svc = MeetingService(db, MagicMock(), MagicMock())

        participants = [
            {"speaker_label": "Speaker 0", "speaker_name": "Alice"},
            {"speaker_label": "Speaker 1"},
        ]
        result = await svc.add_participants(uuid.uuid4(), participants)
        assert len(result) == 2
        assert all(isinstance(p, MeetingParticipant) for p in result)


class TestMeetingServiceListMeetings:
    @pytest.mark.asyncio
    async def test_list_meetings_pagination(self):
        meetings = [_make_meeting() for _ in range(3)]
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result(meetings))
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.list_meetings(uuid.uuid4(), limit=50)
        assert result["has_more"] is False
        assert len(result["items"]) == 3


class TestMeetingServiceCountMeetings:
    @pytest.mark.asyncio
    async def test_count_meetings(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_result(5))
        svc = MeetingService(db, MagicMock(), MagicMock())

        result = await svc.count_meetings(uuid.uuid4())
        assert result == 5


class TestMeetingServicePresignedUpload:
    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url(self):
        s3 = AsyncMock()
        s3.generate_presigned_upload_url = AsyncMock(return_value={
            "url": "https://s3.amazonaws.com/bucket/key",
            "fields": {"key": "value"},
        })
        svc = MeetingService(_mock_db(), s3, MagicMock())

        result = await svc.generate_presigned_upload_url(
            uuid.uuid4(), uuid.uuid4(), "audio.mp3", "audio/mpeg",
        )
        assert "s3_key" in result
        assert "upload_url" in result
        assert result["upload_url"] == "https://s3.amazonaws.com/bucket/key"


# ═══════════════════════════════════════════════════════════════════════════════
# DocumentService
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentServiceInstantiation:
    def test_stores_deps(self):
        db = _mock_db()
        s3 = MagicMock()
        settings = MagicMock()
        svc = DocumentService(db, s3, settings)
        assert svc.db is db
        assert svc.s3_client is s3


class TestDocumentServiceDetectType:
    def test_content_type_pdf(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        assert svc._detect_document_type("x.pdf", "application/pdf") == "pdf"

    def test_content_type_docx(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert svc._detect_document_type("x.docx", ct) == "docx"

    def test_content_type_xlsx(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert svc._detect_document_type("x.xlsx", ct) == "xlsx"

    def test_content_type_pptx(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        ct = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert svc._detect_document_type("x.pptx", ct) == "pptx"

    def test_content_type_txt(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        assert svc._detect_document_type("x.txt", "text/plain") == "txt"

    def test_fallback_to_extension(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        assert svc._detect_document_type("report.pdf", "application/octet-stream") == "pdf"

    def test_unknown_type(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        assert svc._detect_document_type("data.bin", "application/octet-stream") == "unknown"

    def test_no_extension(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        assert svc._detect_document_type("README", "application/octet-stream") == "unknown"


class TestDocumentServiceUpload:
    @pytest.mark.asyncio
    async def test_upload_document_creates_record(self):
        db = _mock_db()
        svc = DocumentService(db, MagicMock(), MagicMock())

        result = await svc.upload_document(
            deal_id=uuid.uuid4(), org_id=uuid.uuid4(),
            filename="report.pdf", s3_key="s3/key",
            content_type="application/pdf", file_size=1024,
            uploaded_by=uuid.uuid4(),
        )
        assert isinstance(result, Document)
        assert result.document_type == "pdf"
        db.add.assert_called_once()


class TestDocumentServiceGetDocument:
    @pytest.mark.asyncio
    async def test_get_document_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = DocumentService(db, MagicMock(), MagicMock())

        with pytest.raises(NotFoundError):
            await svc.get_document(uuid.uuid4())


class TestDocumentServiceDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_document_removes_s3_and_db(self):
        doc = _make_document()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(doc))
        s3 = AsyncMock()
        svc = DocumentService(db, s3, MagicMock())

        await svc.delete_document(doc.id)
        s3.delete_file.assert_awaited_once_with(doc.file_key)
        db.delete.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_delete_document_s3_failure_does_not_block(self):
        doc = _make_document()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(doc))
        s3 = AsyncMock()
        s3.delete_file = AsyncMock(side_effect=Exception("S3 error"))
        svc = DocumentService(db, s3, MagicMock())

        await svc.delete_document(doc.id)
        db.delete.assert_awaited_once()


class TestDocumentServiceUpdateExtractedText:
    @pytest.mark.asyncio
    async def test_update_extracted_text(self):
        doc = _make_document()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(doc))
        svc = DocumentService(db, MagicMock(), MagicMock())

        result = await svc.update_extracted_text(doc.id, "Extracted content here")
        assert result.extracted_text == "Extracted content here"


class TestDocumentServiceGenerateDownloadUrl:
    @pytest.mark.asyncio
    async def test_generate_download_url(self):
        doc = _make_document()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(doc))
        s3 = AsyncMock()
        s3.generate_presigned_download_url = AsyncMock(return_value="https://presigned-url")
        svc = DocumentService(db, s3, MagicMock())

        result = await svc.generate_download_url(doc.id)
        assert result == "https://presigned-url"


class TestDocumentServiceS3Key:
    def test_s3_key_format(self):
        svc = DocumentService(_mock_db(), MagicMock(), MagicMock())
        org_id, deal_id = uuid.uuid4(), uuid.uuid4()
        key = svc._s3_key(org_id, deal_id, "report.pdf")
        assert key.startswith(f"orgs/{org_id}/deals/{deal_id}/documents/")
        assert key.endswith("/report.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# AnalysisService
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalysisServiceInstantiation:
    def test_stores_deps(self):
        db = _mock_db()
        llm = MagicMock()
        svc = AnalysisService(db, llm)
        assert svc.db is db
        assert svc.llm_router is llm
        assert svc.transcript_service is not None  # auto-created


class TestAnalysisServiceParseLLMOutput:
    def test_valid_json(self):
        result = AnalysisService._parse_llm_output('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        text = '```json\n{"key": "value"}\n```'
        result = AnalysisService._parse_llm_output(text)
        assert result == {"key": "value"}

    def test_json_with_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        result = AnalysisService._parse_llm_output(text)
        assert result == {"key": "value"}

    def test_invalid_json_returns_raw(self):
        result = AnalysisService._parse_llm_output("not json at all")
        assert result["parse_error"] is True
        assert result["raw_output"] == "not json at all"

    def test_empty_string(self):
        result = AnalysisService._parse_llm_output("")
        assert result["parse_error"] is True

    def test_nested_json(self):
        data = {"analysis": {"topics": ["revenue", "growth"], "score": 0.95}}
        result = AnalysisService._parse_llm_output(json.dumps(data))
        assert result == data

    def test_whitespace_padded_json(self):
        result = AnalysisService._parse_llm_output('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}


class TestAnalysisServiceGetAnalysis:
    @pytest.mark.asyncio
    async def test_get_analysis_not_found_raises(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = AnalysisService(db, MagicMock())

        with pytest.raises(NotFoundError):
            await svc.get_analysis(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_analysis_success(self):
        analysis = _make_analysis()
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(analysis))
        svc = AnalysisService(db, MagicMock())

        result = await svc.get_analysis(analysis.id)
        assert result is analysis


class TestAnalysisServiceGetLatestAnalysis:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_analysis(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))
        svc = AnalysisService(db, MagicMock())

        result = await svc.get_latest_analysis(uuid.uuid4(), "diligence")
        assert result is None


class TestAnalysisServiceListAnalyses:
    @pytest.mark.asyncio
    async def test_list_analyses(self):
        analyses = [_make_analysis(), _make_analysis()]
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result(analyses))
        svc = AnalysisService(db, MagicMock())

        result = await svc.list_analyses(uuid.uuid4())
        assert len(result) == 2


class TestAnalysisServiceNextVersion:
    @pytest.mark.asyncio
    async def test_first_version_is_1(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_result(0))
        svc = AnalysisService(db, MagicMock())

        version = await svc._next_version(uuid.uuid4(), "diligence")
        assert version == 1

    @pytest.mark.asyncio
    async def test_increments_version(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_result(3))
        svc = AnalysisService(db, MagicMock())

        version = await svc._next_version(uuid.uuid4(), "diligence")
        assert version == 4


# ═══════════════════════════════════════════════════════════════════════════════
# QAService
# ═══════════════════════════════════════════════════════════════════════════════

class TestQAServiceInstantiation:
    def test_stores_deps(self):
        db = _mock_db()
        llm = MagicMock()
        embedding = MagicMock()
        svc = QAService(db, llm, embedding)
        assert svc.db is db
        assert svc.llm_router is llm
        assert svc.embedding_service is embedding
        assert svc.guardrails is not None

    def test_default_top_k(self):
        assert QAService.DEFAULT_TOP_K == 15


class TestQAServiceFormatContext:
    def test_format_context_basic(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        results = [
            {"source_type": "transcript", "text": "Hello world", "metadata": {}},
            {"source_type": "document", "text": "Financial data", "metadata": {"page": 3}},
        ]

        context = svc._format_context(results)
        assert "chunk_0" in context
        assert "chunk_1" in context
        assert "transcript" in context
        assert "Hello world" in context
        assert "Page: 3" in context

    def test_format_context_with_speaker(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        results = [
            {
                "source_type": "transcript",
                "text": "Revenue grew",
                "metadata": {"speaker_name": "CFO", "start_time": 120.5},
            },
        ]
        context = svc._format_context(results)
        assert "Speaker: CFO" in context
        assert "Time: 120.5s" in context


class TestQAServiceParseResponse:
    def test_parse_valid_json(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        resp = json.dumps({"answer": "Revenue increased", "confidence": "high"})
        result = svc._parse_response(resp)
        assert result["answer"] == "Revenue increased"

    def test_parse_markdown_fenced_json(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        resp = '```json\n{"answer": "test"}\n```'
        result = svc._parse_response(resp)
        assert result["answer"] == "test"

    def test_parse_plain_text_fallback(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        result = svc._parse_response("This is a plain text answer.")
        assert result["answer"] == "This is a plain text answer."


class TestQAServiceMapCitations:
    def test_maps_valid_citations(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        search_results = [
            {"source_type": "transcript", "text": "Revenue grew 20%", "metadata": {}},
            {"source_type": "document", "text": "Gross margin improved", "metadata": {}},
        ]
        raw_citations = [
            {"chunk_id": "chunk_0", "relevance": "direct"},
            {"chunk_id": "chunk_1", "relevance": "supporting"},
        ]

        citations = svc._map_citations(raw_citations, search_results)
        assert len(citations) == 2
        assert citations[0].chunk_id == "chunk_0"
        assert citations[0].source_type == "transcript"
        assert citations[1].relevance == "supporting"

    def test_ignores_invalid_chunk_ids(self):
        svc = QAService(_mock_db(), MagicMock(), MagicMock())
        search_results = [
            {"source_type": "transcript", "text": "text", "metadata": {}},
        ]
        raw_citations = [{"chunk_id": "chunk_999"}]

        citations = svc._map_citations(raw_citations, search_results)
        assert len(citations) == 0


class TestQAServiceAsk:
    @pytest.mark.asyncio
    async def test_no_search_results_returns_low_confidence(self):
        db = _mock_db()
        llm = AsyncMock()
        embedding = AsyncMock()
        embedding.search = AsyncMock(return_value=[])
        svc = QAService(db, llm, embedding)

        result = await svc.ask(uuid.uuid4(), uuid.uuid4(), "What is the revenue?")
        assert isinstance(result, QAResponse)
        assert result.confidence == "low"
        assert len(result.citations) == 0
        assert "could not find" in result.answer.lower()


class TestQAServiceDataclasses:
    def test_citation_dataclass(self):
        c = Citation(chunk_id="c0", source_type="transcript", text="hello")
        assert c.relevance == "direct"  # default
        assert c.metadata == {}  # default

    def test_qa_response_dataclass(self):
        r = QAResponse(
            answer="test", citations=[], confidence="high",
            source_coverage="full",
        )
        assert r.grounding_score is None
        assert r.grounding_status == "pending"


# ═══════════════════════════════════════════════════════════════════════════════
# AuditService
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditServiceInstantiation:
    def test_stores_db(self):
        db = _mock_db()
        svc = AuditService(db)
        assert svc.db is db


class TestAuditServiceLog:
    @pytest.mark.asyncio
    async def test_log_creates_entry(self):
        db = _mock_db()
        added = []
        db.add = lambda obj: added.append(obj)
        svc = AuditService(db)

        org_id, user_id = uuid.uuid4(), uuid.uuid4()
        result = await svc.log(
            org_id=org_id,
            user_id=user_id,
            action="create",
            resource_type="deal",
            resource_id=uuid.uuid4(),
            details={"name": "New Deal"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert isinstance(result, AuditLog)
        assert result.action == "create"
        assert result.resource_type == "deal"
        assert len(added) == 1

    @pytest.mark.asyncio
    async def test_log_without_optional_fields(self):
        db = _mock_db()
        svc = AuditService(db)

        result = await svc.log(
            org_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            action="read",
            resource_type="meeting",
        )
        assert isinstance(result, AuditLog)
        db.flush.assert_awaited_once()


class TestAuditServiceQueryLogs:
    @pytest.mark.asyncio
    async def test_query_logs_returns_paginated_result(self):
        logs = [_make_audit_log() for _ in range(3)]
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result(logs))
        svc = AuditService(db)

        result = await svc.query_logs(uuid.uuid4())
        assert "items" in result
        assert "cursor" in result
        assert "has_more" in result
        assert len(result["items"]) == 3
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_query_logs_empty_results(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalars_all_result([]))
        svc = AuditService(db)

        result = await svc.query_logs(uuid.uuid4())
        assert result["items"] == []
        assert result["has_more"] is False
        assert result["cursor"] is None


class TestAuditServiceCountLogs:
    @pytest.mark.asyncio
    async def test_count_logs(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_result(42))
        svc = AuditService(db)

        result = await svc.count_logs(uuid.uuid4())
        assert result == 42

    @pytest.mark.asyncio
    async def test_count_logs_with_date_range(self):
        db = _mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_result(10))
        svc = AuditService(db)

        result = await svc.count_logs(
            uuid.uuid4(),
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 12, 31, tzinfo=UTC),
        )
        assert result == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-cutting: Exception hierarchy
# ═══════════════════════════════════════════════════════════════════════════════

class TestExceptionHierarchy:
    def test_not_found_error(self):
        e = NotFoundError("Deal", "abc-123")
        assert e.status_code == 404
        assert "abc-123" in e.message
        assert e.code == "NOT_FOUND"

    def test_not_found_error_without_id(self):
        e = NotFoundError("Deal")
        assert "Deal not found" in e.message

    def test_permission_denied_error(self):
        e = PermissionDeniedError("Access denied")
        assert e.status_code == 403
        assert e.code == "PERMISSION_DENIED"

    def test_conflict_error(self):
        e = ConflictError("Already exists")
        assert e.status_code == 409
        assert e.code == "CONFLICT"
