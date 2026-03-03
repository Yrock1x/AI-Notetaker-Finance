"""Comprehensive tests for the backend/app/core module.

Covers:
  - security.py: OrgRole, DealRole enums, role hierarchy, permissions,
    verify_org_membership, verify_deal_membership
  - exceptions.py: All custom exceptions and the exception handler factory
  - config.py: Settings validation, defaults, env-variable handling, properties
  - middleware.py: RequestIDMiddleware, RequestLoggingMiddleware,
    OrgContextMiddleware, AuditLogMiddleware helpers (_parse_resource,
    _method_to_action, _get_client_ip, _is_uuid)
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException

# ---------------------------------------------------------------------------
# security.py
# ---------------------------------------------------------------------------
from app.core.security import (
    DEAL_ROLE_HIERARCHY,
    DEAL_ROLE_PERMISSIONS,
    DealRole,
    OrgRole,
    verify_deal_membership,
    verify_org_membership,
)

# --- Enum membership & values ---


class TestOrgRole:
    def test_owner_value(self):
        assert OrgRole.OWNER == "owner"

    def test_admin_value(self):
        assert OrgRole.ADMIN == "admin"

    def test_member_value(self):
        assert OrgRole.MEMBER == "member"

    def test_member_count(self):
        assert len(OrgRole) == 3

    def test_str_enum_behaviour(self):
        """OrgRole members should behave as plain strings."""
        assert f"role is {OrgRole.OWNER}" == "role is owner"


class TestDealRole:
    def test_lead_value(self):
        assert DealRole.LEAD == "lead"

    def test_admin_value(self):
        assert DealRole.ADMIN == "admin"

    def test_analyst_value(self):
        assert DealRole.ANALYST == "analyst"

    def test_viewer_value(self):
        assert DealRole.VIEWER == "viewer"

    def test_member_count(self):
        assert len(DealRole) == 4


# --- Hierarchy ---


class TestDealRoleHierarchy:
    def test_viewer_is_lowest(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.VIEWER] == 0

    def test_analyst_above_viewer(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.ANALYST] > DEAL_ROLE_HIERARCHY[DealRole.VIEWER]

    def test_admin_above_analyst(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.ADMIN] > DEAL_ROLE_HIERARCHY[DealRole.ANALYST]

    def test_lead_is_highest(self):
        assert DEAL_ROLE_HIERARCHY[DealRole.LEAD] == max(DEAL_ROLE_HIERARCHY.values())

    def test_all_roles_present(self):
        for role in DealRole:
            assert role in DEAL_ROLE_HIERARCHY

    def test_strict_ordering(self):
        """The full ordering should be VIEWER < ANALYST < ADMIN < LEAD."""
        v = DEAL_ROLE_HIERARCHY[DealRole.VIEWER]
        a = DEAL_ROLE_HIERARCHY[DealRole.ANALYST]
        ad = DEAL_ROLE_HIERARCHY[DealRole.ADMIN]
        lead = DEAL_ROLE_HIERARCHY[DealRole.LEAD]
        assert v < a < ad < lead


# --- Permissions ---


class TestDealRolePermissions:
    def test_viewer_read_only(self):
        assert DEAL_ROLE_PERMISSIONS[DealRole.VIEWER] == {"read"}

    def test_analyst_permissions(self):
        assert DEAL_ROLE_PERMISSIONS[DealRole.ANALYST] == {"read", "write", "run_analysis"}

    def test_admin_permissions(self):
        expected = {"read", "write", "manage_members", "run_analysis", "export"}
        assert DEAL_ROLE_PERMISSIONS[DealRole.ADMIN] == expected

    def test_lead_has_all_permissions(self):
        lead_perms = DEAL_ROLE_PERMISSIONS[DealRole.LEAD]
        for role_perms in DEAL_ROLE_PERMISSIONS.values():
            assert role_perms.issubset(lead_perms)

    def test_lead_has_delete(self):
        assert "delete" in DEAL_ROLE_PERMISSIONS[DealRole.LEAD]

    def test_lead_has_manage_settings(self):
        assert "manage_settings" in DEAL_ROLE_PERMISSIONS[DealRole.LEAD]

    def test_viewer_cannot_write(self):
        assert "write" not in DEAL_ROLE_PERMISSIONS[DealRole.VIEWER]

    def test_analyst_cannot_delete(self):
        assert "delete" not in DEAL_ROLE_PERMISSIONS[DealRole.ANALYST]

    def test_admin_cannot_delete(self):
        assert "delete" not in DEAL_ROLE_PERMISSIONS[DealRole.ADMIN]

    def test_all_roles_have_read(self):
        for role in DealRole:
            assert "read" in DEAL_ROLE_PERMISSIONS[role]


# --- verify_org_membership ---


def _make_db_mock(return_value):
    """Helper: create an AsyncSession mock whose execute().scalar_one_or_none()
    returns *return_value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


class TestVerifyOrgMembership:
    async def test_raises_404_when_not_member(self):
        db = _make_db_mock(None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_org_membership(db, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    async def test_passes_when_member_no_min_role(self):
        membership = SimpleNamespace(role=OrgRole.MEMBER)
        db = _make_db_mock(membership)
        # Should not raise
        await verify_org_membership(db, uuid.uuid4(), uuid.uuid4())

    async def test_raises_403_when_role_too_low(self):
        membership = SimpleNamespace(role=OrgRole.MEMBER)
        db = _make_db_mock(membership)
        with pytest.raises(HTTPException) as exc_info:
            await verify_org_membership(db, uuid.uuid4(), uuid.uuid4(), min_role=OrgRole.ADMIN)
        assert exc_info.value.status_code == 403

    async def test_passes_when_role_equal(self):
        membership = SimpleNamespace(role=OrgRole.ADMIN)
        db = _make_db_mock(membership)
        await verify_org_membership(db, uuid.uuid4(), uuid.uuid4(), min_role=OrgRole.ADMIN)

    async def test_passes_when_role_higher(self):
        membership = SimpleNamespace(role=OrgRole.OWNER)
        db = _make_db_mock(membership)
        await verify_org_membership(db, uuid.uuid4(), uuid.uuid4(), min_role=OrgRole.ADMIN)

    async def test_owner_passes_all_min_roles(self):
        membership = SimpleNamespace(role=OrgRole.OWNER)
        db = _make_db_mock(membership)
        for role in OrgRole:
            await verify_org_membership(db, uuid.uuid4(), uuid.uuid4(), min_role=role)


# --- verify_deal_membership ---


class TestVerifyDealMembership:
    async def test_raises_404_when_not_member(self):
        db = _make_db_mock(None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_deal_membership(db, uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    async def test_passes_when_member_no_constraints(self):
        membership = SimpleNamespace(role=DealRole.VIEWER)
        db = _make_db_mock(membership)
        await verify_deal_membership(db, uuid.uuid4(), uuid.uuid4())

    async def test_raises_403_when_deal_role_too_low(self):
        membership = SimpleNamespace(role=DealRole.VIEWER)
        db = _make_db_mock(membership)
        with pytest.raises(HTTPException) as exc_info:
            await verify_deal_membership(
                db, uuid.uuid4(), uuid.uuid4(), min_role=DealRole.ANALYST
            )
        assert exc_info.value.status_code == 403

    async def test_passes_when_deal_role_equal(self):
        membership = SimpleNamespace(role=DealRole.ANALYST)
        db = _make_db_mock(membership)
        await verify_deal_membership(
            db, uuid.uuid4(), uuid.uuid4(), min_role=DealRole.ANALYST
        )

    async def test_passes_when_deal_role_higher(self):
        membership = SimpleNamespace(role=DealRole.LEAD)
        db = _make_db_mock(membership)
        await verify_deal_membership(
            db, uuid.uuid4(), uuid.uuid4(), min_role=DealRole.ADMIN
        )

    async def test_raises_403_when_missing_permission(self):
        membership = SimpleNamespace(role=DealRole.VIEWER)
        db = _make_db_mock(membership)
        with pytest.raises(HTTPException) as exc_info:
            await verify_deal_membership(
                db, uuid.uuid4(), uuid.uuid4(), required_permission="write"
            )
        assert exc_info.value.status_code == 403
        assert "write" in exc_info.value.detail

    async def test_passes_when_has_permission(self):
        membership = SimpleNamespace(role=DealRole.ANALYST)
        db = _make_db_mock(membership)
        await verify_deal_membership(
            db, uuid.uuid4(), uuid.uuid4(), required_permission="write"
        )

    async def test_lead_has_all_permissions(self):
        membership = SimpleNamespace(role=DealRole.LEAD)
        db = _make_db_mock(membership)
        all_perms = set()
        for p in DEAL_ROLE_PERMISSIONS.values():
            all_perms |= p
        for perm in all_perms:
            await verify_deal_membership(
                db, uuid.uuid4(), uuid.uuid4(), required_permission=perm
            )

    async def test_min_role_and_permission_both_checked(self):
        """When both min_role and required_permission are given, both must pass."""
        membership = SimpleNamespace(role=DealRole.ANALYST)
        db = _make_db_mock(membership)
        # Analyst has write but not delete
        with pytest.raises(HTTPException) as exc_info:
            await verify_deal_membership(
                db,
                uuid.uuid4(),
                uuid.uuid4(),
                min_role=DealRole.VIEWER,
                required_permission="delete",
            )
        assert exc_info.value.status_code == 403

    async def test_min_role_fails_before_permission_check(self):
        """If min_role check fails, permission is never reached."""
        membership = SimpleNamespace(role=DealRole.VIEWER)
        db = _make_db_mock(membership)
        with pytest.raises(HTTPException) as exc_info:
            await verify_deal_membership(
                db,
                uuid.uuid4(),
                uuid.uuid4(),
                min_role=DealRole.LEAD,
                required_permission="read",
            )
        assert exc_info.value.status_code == 403
        assert "lead" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# exceptions.py
# ---------------------------------------------------------------------------
from app.core.exceptions import (  # noqa: E402
    ConflictError,
    DealWiseError,
    DomainValidationError,
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    register_exception_handlers,
)


class TestDealWiseError:
    def test_defaults(self):
        err = DealWiseError("boom")
        assert err.message == "boom"
        assert err.code == "INTERNAL_ERROR"
        assert err.status_code == 500

    def test_custom_code_and_status(self):
        err = DealWiseError("x", code="CUSTOM", status_code=418)
        assert err.code == "CUSTOM"
        assert err.status_code == 418

    def test_str_is_message(self):
        err = DealWiseError("hello")
        assert str(err) == "hello"

    def test_is_exception(self):
        assert issubclass(DealWiseError, Exception)


class TestNotFoundError:
    def test_without_id(self):
        err = NotFoundError("Deal")
        assert err.message == "Deal not found"
        assert err.code == "NOT_FOUND"
        assert err.status_code == 404

    def test_with_id(self):
        err = NotFoundError("Deal", "abc-123")
        assert err.message == "Deal 'abc-123' not found"

    def test_inherits_dealwise_error(self):
        assert issubclass(NotFoundError, DealWiseError)


class TestPermissionDeniedError:
    def test_default_message(self):
        err = PermissionDeniedError()
        assert err.message == "Permission denied"
        assert err.status_code == 403

    def test_custom_message(self):
        err = PermissionDeniedError("Nope")
        assert err.message == "Nope"

    def test_code(self):
        err = PermissionDeniedError()
        assert err.code == "PERMISSION_DENIED"


class TestConflictError:
    def test_attributes(self):
        err = ConflictError("duplicate")
        assert err.message == "duplicate"
        assert err.code == "CONFLICT"
        assert err.status_code == 409


class TestDomainValidationError:
    def test_attributes(self):
        err = DomainValidationError("bad field")
        assert err.message == "bad field"
        assert err.code == "VALIDATION_ERROR"
        assert err.status_code == 422


class TestExternalServiceError:
    def test_message_format(self):
        err = ExternalServiceError("Deepgram", "timeout")
        assert err.message == "Deepgram error: timeout"
        assert err.code == "EXTERNAL_SERVICE_ERROR"
        assert err.status_code == 502


class TestRateLimitError:
    def test_default_message(self):
        err = RateLimitError()
        assert err.message == "Rate limit exceeded"
        assert err.status_code == 429
        assert err.code == "RATE_LIMIT"

    def test_custom_message(self):
        err = RateLimitError("slow down")
        assert err.message == "slow down"


class TestExceptionHandlerRegistration:
    def test_register_exception_handlers_adds_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        # FastAPI stores handlers keyed by exception class
        assert DealWiseError in app.exception_handlers
        assert Exception in app.exception_handlers


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------
from app.core.config import Settings  # noqa: E402


class TestSettingsDefaults:
    """Test that Settings has correct default values."""

    def test_app_env_default(self):
        s = Settings()
        assert s.app_env == "development"

    def test_app_name_default(self):
        s = Settings()
        assert s.app_name == "Deal Companion"

    def test_log_level_default(self):
        s = Settings()
        assert s.log_level == "INFO"

    def test_database_url_default(self):
        s = Settings()
        assert "postgresql" in s.database_url

    def test_redis_url_default(self):
        s = Settings()
        assert s.redis_url == "redis://localhost:6379/0"

    def test_s3_bucket_default(self):
        s = Settings()
        assert s.s3_bucket_name == "dealwise-local"

    def test_s3_endpoint_url_default_none(self):
        s = Settings()
        assert s.s3_endpoint_url is None

    def test_aws_region_default(self):
        s = Settings()
        assert s.aws_region == "us-east-1"

    def test_demo_mode_default_false(self):
        s = Settings()
        assert s.demo_mode is False

    def test_db_pool_size_default(self):
        s = Settings()
        assert s.db_pool_size == 20

    def test_db_max_overflow_default(self):
        s = Settings()
        assert s.db_max_overflow == 10

    def test_cognito_fields_empty_by_default(self):
        s = Settings()
        assert s.cognito_user_pool_id == ""
        assert s.cognito_app_client_id == ""
        assert s.cognito_domain == ""

    def test_api_keys_empty_by_default(self):
        s = Settings()
        assert s.anthropic_api_key == ""
        assert s.openai_api_key == ""
        assert s.deepgram_api_key == ""


class TestSettingsProperties:
    def test_cors_origin_list_single(self):
        s = Settings(cors_origins="http://localhost:3000")
        assert s.cors_origin_list == ["http://localhost:3000"]

    def test_cors_origin_list_multiple(self):
        s = Settings(cors_origins="http://a.com, http://b.com")
        assert s.cors_origin_list == ["http://a.com", "http://b.com"]

    def test_is_production_true(self):
        s = Settings(app_env="production")
        assert s.is_production is True

    def test_is_production_false_for_dev(self):
        s = Settings(app_env="development")
        assert s.is_production is False

    def test_is_production_false_for_staging(self):
        s = Settings(app_env="staging")
        assert s.is_production is False

    def test_async_database_url_conversion(self):
        s = Settings(database_url="postgresql://user:pass@localhost/db")
        assert s.async_database_url == "postgresql+asyncpg://user:pass@localhost/db"

    def test_async_database_url_already_async(self):
        url = "postgresql+asyncpg://user:pass@localhost/db"
        s = Settings(database_url=url)
        assert s.async_database_url == url


class TestSettingsValidation:
    def test_invalid_app_env(self):
        with pytest.raises(ValueError):
            Settings(app_env="invalid_env")

    def test_demo_mode_in_production_raises(self):
        with pytest.raises(ValueError, match="Demo mode cannot be enabled in production"):
            Settings(
                app_env="production",
                demo_mode=True,
                demo_jwt_secret="some-changed-secret",  # noqa: S106
            )

    def test_demo_mode_with_default_secret_raises(self):
        with pytest.raises(ValueError, match="demo_jwt_secret must be changed"):
            Settings(
                app_env="development",
                demo_mode=True,
                # demo_jwt_secret left at default
            )

    def test_demo_mode_valid_in_development(self):
        s = Settings(
            app_env="development",
            demo_mode=True,
            demo_jwt_secret="a-real-secret",  # noqa: S106
        )
        assert s.demo_mode is True

    def test_demo_mode_valid_in_staging(self):
        s = Settings(
            app_env="staging",
            demo_mode=True,
            demo_jwt_secret="a-real-secret",  # noqa: S106
        )
        assert s.demo_mode is True


class TestSettingsFromEnv:
    def test_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("APP_NAME", "TestApp")
        s = Settings()
        assert s.app_name == "TestApp"

    def test_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_env_redis_url(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://prod:6379/1")
        s = Settings()
        assert s.redis_url == "redis://prod:6379/1"

    def test_env_s3_bucket(self, monkeypatch):
        monkeypatch.setenv("S3_BUCKET_NAME", "prod-bucket")
        s = Settings()
        assert s.s3_bucket_name == "prod-bucket"

    def test_env_demo_mode_true(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        monkeypatch.setenv("DEMO_JWT_SECRET", "not-default")
        s = Settings()
        assert s.demo_mode is True


# ---------------------------------------------------------------------------
# middleware.py
# ---------------------------------------------------------------------------
from app.core.middleware import (  # noqa: E402
    SKIP_AUDIT_PATHS,
    AuditLogMiddleware,
    _is_uuid,
)


class TestIsUuid:
    def test_valid_uuid(self):
        assert _is_uuid(str(uuid.uuid4())) is True

    def test_invalid_string(self):
        assert _is_uuid("not-a-uuid") is False

    def test_empty_string(self):
        assert _is_uuid("") is False

    def test_partial_uuid(self):
        assert _is_uuid("12345678-1234-1234-1234") is False

    def test_uuid_without_hyphens(self):
        uid = uuid.uuid4()
        assert _is_uuid(uid.hex) is True  # UUID() accepts hex without hyphens


class TestSkipAuditPaths:
    def test_health_in_skip(self):
        assert "/health" in SKIP_AUDIT_PATHS

    def test_health_ready_in_skip(self):
        assert "/health/ready" in SKIP_AUDIT_PATHS

    def test_docs_in_skip(self):
        assert "/docs" in SKIP_AUDIT_PATHS

    def test_redoc_in_skip(self):
        assert "/redoc" in SKIP_AUDIT_PATHS

    def test_openapi_in_skip(self):
        assert "/openapi.json" in SKIP_AUDIT_PATHS


class TestAuditLogParseResource:
    """Test AuditLogMiddleware._parse_resource static method."""

    def test_deals_path(self):
        uid = str(uuid.uuid4())
        rtype, rid, did = AuditLogMiddleware._parse_resource(f"/api/v1/deals/{uid}")
        assert rtype == "deal"
        assert rid == uid
        assert did == uid

    def test_meetings_under_deal(self):
        deal_uid = str(uuid.uuid4())
        meeting_uid = str(uuid.uuid4())
        rtype, rid, did = AuditLogMiddleware._parse_resource(
            f"/api/v1/deals/{deal_uid}/meetings/{meeting_uid}"
        )
        assert rtype == "meeting"
        assert rid == meeting_uid
        assert did == deal_uid

    def test_orgs_path(self):
        uid = str(uuid.uuid4())
        rtype, rid, did = AuditLogMiddleware._parse_resource(f"/api/v1/orgs/{uid}")
        assert rtype == "organization"
        assert rid == uid
        assert did is None

    def test_documents_path(self):
        deal_uid = str(uuid.uuid4())
        doc_uid = str(uuid.uuid4())
        rtype, rid, did = AuditLogMiddleware._parse_resource(
            f"/api/v1/deals/{deal_uid}/documents/{doc_uid}"
        )
        assert rtype == "document"
        assert rid == doc_uid
        assert did == deal_uid

    def test_unknown_resource(self):
        rtype, rid, did = AuditLogMiddleware._parse_resource("/api/v1/unknown")
        assert rtype is None
        assert rid is None
        assert did is None

    def test_root_path(self):
        rtype, rid, did = AuditLogMiddleware._parse_resource("/")
        assert rtype is None

    def test_analyses_path(self):
        deal_uid = str(uuid.uuid4())
        analysis_uid = str(uuid.uuid4())
        rtype, rid, did = AuditLogMiddleware._parse_resource(
            f"/api/v1/deals/{deal_uid}/analyses/{analysis_uid}"
        )
        assert rtype == "analysis"
        assert rid == analysis_uid
        assert did == deal_uid


class TestAuditLogMethodToAction:
    def test_post_creates(self):
        assert AuditLogMiddleware._method_to_action("POST", "deal") == "create_deal"

    def test_put_updates(self):
        assert AuditLogMiddleware._method_to_action("PUT", "meeting") == "update_meeting"

    def test_patch_updates(self):
        assert AuditLogMiddleware._method_to_action("PATCH", "meeting") == "update_meeting"

    def test_delete_deletes(self):
        assert AuditLogMiddleware._method_to_action("DELETE", "deal") == "delete_deal"

    def test_no_resource_type(self):
        assert AuditLogMiddleware._method_to_action("POST", None) == "create"

    def test_unknown_method(self):
        assert AuditLogMiddleware._method_to_action("OPTIONS", "deal") == "options_deal"


class TestAuditLogGetClientIp:
    def test_forwarded_for(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert AuditLogMiddleware._get_client_ip(request) == "1.2.3.4"

    def test_direct_client(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert AuditLogMiddleware._get_client_ip(request) == "10.0.0.1"

    def test_no_client(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert AuditLogMiddleware._get_client_ip(request) == "unknown"

    def test_forwarded_for_single(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "  9.8.7.6  "}
        assert AuditLogMiddleware._get_client_ip(request) == "9.8.7.6"


class TestAuditLogMutatingMethods:
    def test_mutating_methods_set(self):
        assert {"POST", "PUT", "PATCH", "DELETE"} == AuditLogMiddleware.MUTATING_METHODS

    def test_get_not_mutating(self):
        assert "GET" not in AuditLogMiddleware.MUTATING_METHODS

    def test_head_not_mutating(self):
        assert "HEAD" not in AuditLogMiddleware.MUTATING_METHODS

    def test_options_not_mutating(self):
        assert "OPTIONS" not in AuditLogMiddleware.MUTATING_METHODS
