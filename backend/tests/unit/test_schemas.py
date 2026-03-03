"""
Comprehensive tests for all Pydantic schemas in app.schemas.

Tests cover:
- Valid data creates models correctly
- Required field validation (missing fields raise ValidationError)
- Type validation (wrong types raise errors)
- Optional/default field handling
- Custom validators and field constraints (min_length, max_length, pattern, ge, le)
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# ─── analysis.py ─────────────────────────────────────────────────────────────
from app.schemas.analysis import AnalysisRequest, AnalysisResponse

# ─── audit.py ────────────────────────────────────────────────────────────────
from app.schemas.audit import AuditLogQuery, AuditLogResponse

# ─── common.py ───────────────────────────────────────────────────────────────
from app.schemas.common import (
    BaseSchema,
    CursorParams,
    ErrorResponse,
    IDResponse,
    PaginatedResponse,
    SuccessResponse,
)

# ─── deal.py ─────────────────────────────────────────────────────────────────
from app.schemas.deal import (
    DealCreate,
    DealMemberCreate,
    DealMemberResponse,
    DealResponse,
    DealUpdate,
)

# ─── document.py ─────────────────────────────────────────────────────────────
from app.schemas.document import (
    DocumentCreate,
    DocumentDownloadResponse,
    DocumentResponse,
    DocumentUploadResponse,
)

# ─── integration.py ──────────────────────────────────────────────────────────
from app.schemas.integration import (
    BotSessionCreate,
    BotSessionResponse,
    IntegrationResponse,
    OAuthInitResponse,
    WebhookResponse,
)

# ─── meeting.py ──────────────────────────────────────────────────────────────
from app.schemas.meeting import (
    MeetingCreate,
    MeetingParticipantResponse,
    MeetingResponse,
    MeetingUpdate,
    MeetingUploadResponse,
    UpdateSpeakerName,
)

# ─── organization.py ─────────────────────────────────────────────────────────
from app.schemas.organization import (
    OrgCreate,
    OrgMemberCreate,
    OrgMemberResponse,
    OrgResponse,
    OrgUpdate,
)

# ─── qa.py ───────────────────────────────────────────────────────────────────
from app.schemas.qa import Citation, QAHistoryResponse, QARequest, QAResponse

# ─── transcript.py ───────────────────────────────────────────────────────────
from app.schemas.transcript import TranscriptResponse, TranscriptSegmentResponse

# ─── user.py ─────────────────────────────────────────────────────────────────
from app.schemas.user import UserResponse, UserUpdate

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

NOW = datetime.now(UTC)
UUID1 = uuid.uuid4()
UUID2 = uuid.uuid4()
UUID3 = uuid.uuid4()


# ═══════════════════════════════════════════════════════════════════════════════
# common.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPaginatedResponse:
    def test_valid_paginated_response(self):
        resp = PaginatedResponse[str](items=["a", "b"], cursor="abc123", has_more=True)
        assert resp.items == ["a", "b"]
        assert resp.cursor == "abc123"
        assert resp.has_more is True

    def test_defaults(self):
        resp = PaginatedResponse[int](items=[1, 2, 3])
        assert resp.cursor is None
        assert resp.has_more is False

    def test_empty_items(self):
        resp = PaginatedResponse[str](items=[])
        assert resp.items == []

    def test_missing_items_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PaginatedResponse[str]()
        assert "items" in str(exc_info.value)


class TestCursorParams:
    def test_defaults(self):
        params = CursorParams()
        assert params.cursor is None
        assert params.limit == 25

    def test_custom_values(self):
        params = CursorParams(cursor="next_page", limit=50)
        assert params.cursor == "next_page"
        assert params.limit == 50

    def test_limit_min_boundary(self):
        params = CursorParams(limit=1)
        assert params.limit == 1

    def test_limit_max_boundary(self):
        params = CursorParams(limit=100)
        assert params.limit == 100

    def test_limit_below_min_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CursorParams(limit=0)
        assert "limit" in str(exc_info.value).lower() or "greater" in str(exc_info.value).lower()

    def test_limit_above_max_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CursorParams(limit=101)
        assert "limit" in str(exc_info.value).lower() or "less" in str(exc_info.value).lower()

    def test_limit_negative_raises(self):
        with pytest.raises(ValidationError):
            CursorParams(limit=-1)


class TestErrorResponse:
    def test_valid(self):
        resp = ErrorResponse(code="NOT_FOUND", message="Resource not found")
        assert resp.code == "NOT_FOUND"
        assert resp.message == "Resource not found"
        assert resp.details is None

    def test_with_details(self):
        resp = ErrorResponse(code="VALIDATION", message="Invalid input", details={"field": "name"})
        assert resp.details == {"field": "name"}

    def test_missing_code_raises(self):
        with pytest.raises(ValidationError):
            ErrorResponse(message="Some message")

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            ErrorResponse(code="ERR")


class TestSuccessResponse:
    def test_valid(self):
        resp = SuccessResponse(message="Done")
        assert resp.message == "Done"

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            SuccessResponse()


class TestIDResponse:
    def test_valid(self):
        uid = uuid.uuid4()
        resp = IDResponse(id=uid)
        assert resp.id == uid

    def test_string_uuid_coerced(self):
        uid = uuid.uuid4()
        resp = IDResponse(id=str(uid))
        assert resp.id == uid

    def test_invalid_uuid_raises(self):
        with pytest.raises(ValidationError):
            IDResponse(id="not-a-uuid")

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            IDResponse()


class TestBaseSchema:
    def test_from_attributes_config(self):
        assert BaseSchema.model_config.get("from_attributes") is True


# ═══════════════════════════════════════════════════════════════════════════════
# user.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserResponse:
    def test_valid(self):
        user = UserResponse(
            id=UUID1, email="test@example.com", full_name="Test User", created_at=NOW
        )
        assert user.id == UUID1
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.avatar_url is None
        assert user.is_active is True
        assert user.created_at == NOW

    def test_all_fields(self):
        user = UserResponse(
            id=UUID1,
            email="a@b.com",
            full_name="Alice",
            avatar_url="https://example.com/avatar.png",
            is_active=False,
            created_at=NOW,
        )
        assert user.avatar_url == "https://example.com/avatar.png"
        assert user.is_active is False

    def test_missing_required_email_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserResponse(id=UUID1, full_name="Test", created_at=NOW)
        assert "email" in str(exc_info.value)

    def test_missing_required_full_name_raises(self):
        with pytest.raises(ValidationError):
            UserResponse(id=UUID1, email="test@example.com", created_at=NOW)

    def test_missing_required_id_raises(self):
        with pytest.raises(ValidationError):
            UserResponse(email="test@example.com", full_name="Test", created_at=NOW)

    def test_missing_required_created_at_raises(self):
        with pytest.raises(ValidationError):
            UserResponse(id=UUID1, email="test@example.com", full_name="Test")


class TestUserUpdate:
    def test_empty_update_allowed(self):
        update = UserUpdate()
        assert update.full_name is None
        assert update.avatar_url is None

    def test_partial_update(self):
        update = UserUpdate(full_name="Updated Name")
        assert update.full_name == "Updated Name"
        assert update.avatar_url is None

    def test_full_update(self):
        update = UserUpdate(full_name="Updated", avatar_url="https://example.com/new.png")
        assert update.full_name == "Updated"
        assert update.avatar_url == "https://example.com/new.png"


# ═══════════════════════════════════════════════════════════════════════════════
# organization.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgCreate:
    def test_valid(self):
        org = OrgCreate(name="My Org", slug="my-org")
        assert org.name == "My Org"
        assert org.slug == "my-org"
        assert org.domain is None

    def test_with_domain(self):
        org = OrgCreate(name="My Org", slug="my-org", domain="myorg.com")
        assert org.domain == "myorg.com"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="", slug="my-org")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="x" * 256, slug="my-org")

    def test_name_max_length_ok(self):
        org = OrgCreate(name="x" * 255, slug="my-org")
        assert len(org.name) == 255

    def test_empty_slug_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="My Org", slug="")

    def test_slug_too_long_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="My Org", slug="x" * 101)

    def test_slug_max_length_ok(self):
        org = OrgCreate(name="My Org", slug="x" * 100)
        assert len(org.slug) == 100

    def test_slug_pattern_valid(self):
        org = OrgCreate(name="Org", slug="valid-slug-123")
        assert org.slug == "valid-slug-123"

    def test_slug_pattern_uppercase_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="Org", slug="Invalid-Slug")

    def test_slug_pattern_spaces_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="Org", slug="invalid slug")

    def test_slug_pattern_special_chars_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="Org", slug="invalid_slug!")

    def test_slug_pattern_underscores_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="Org", slug="invalid_slug")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(slug="my-org")

    def test_missing_slug_raises(self):
        with pytest.raises(ValidationError):
            OrgCreate(name="My Org")


class TestOrgUpdate:
    def test_empty_update(self):
        update = OrgUpdate()
        assert update.name is None
        assert update.domain is None
        assert update.settings is None

    def test_partial_update(self):
        update = OrgUpdate(name="New Name")
        assert update.name == "New Name"

    def test_name_min_length_raises(self):
        with pytest.raises(ValidationError):
            OrgUpdate(name="")

    def test_name_max_length_raises(self):
        with pytest.raises(ValidationError):
            OrgUpdate(name="x" * 256)

    def test_settings_dict(self):
        update = OrgUpdate(settings={"theme": "dark"})
        assert update.settings == {"theme": "dark"}


class TestOrgResponse:
    def test_valid(self):
        resp = OrgResponse(id=UUID1, name="Org", slug="org", created_at=NOW)
        assert resp.id == UUID1
        assert resp.name == "Org"
        assert resp.slug == "org"
        assert resp.domain is None
        assert resp.settings is None
        assert resp.created_at == NOW

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            OrgResponse(id=UUID1, slug="org", created_at=NOW)  # missing name


class TestOrgMemberResponse:
    def test_valid(self):
        resp = OrgMemberResponse(
            user_id=UUID1, email="a@b.com", full_name="Alice", role="admin", joined_at=NOW
        )
        assert resp.user_id == UUID1
        assert resp.role == "admin"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            OrgMemberResponse(user_id=UUID1, email="a@b.com", full_name="Alice", joined_at=NOW)


class TestOrgMemberCreate:
    def test_valid_default_role(self):
        member = OrgMemberCreate(email="test@example.com")
        assert member.email == "test@example.com"
        assert member.role == "member"

    def test_custom_role(self):
        member = OrgMemberCreate(email="test@example.com", role="admin")
        assert member.role == "admin"

    def test_owner_role(self):
        member = OrgMemberCreate(email="test@example.com", role="owner")
        assert member.role == "owner"

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            OrgMemberCreate(email="test@example.com", role="superadmin")

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            OrgMemberCreate()


# ═══════════════════════════════════════════════════════════════════════════════
# deal.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDealCreate:
    def test_valid_defaults(self):
        deal = DealCreate(name="Acquisition Target")
        assert deal.name == "Acquisition Target"
        assert deal.description is None
        assert deal.target_company is None
        assert deal.deal_type == "other"
        assert deal.stage is None

    def test_all_fields(self):
        deal = DealCreate(
            name="Deal 1",
            description="Big deal",
            target_company="ACME Corp",
            deal_type="m_and_a",
            stage="LOI",
        )
        assert deal.deal_type == "m_and_a"
        assert deal.target_company == "ACME Corp"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            DealCreate(name="")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            DealCreate(name="x" * 256)

    def test_name_max_length_ok(self):
        deal = DealCreate(name="x" * 255)
        assert len(deal.name) == 255

    def test_invalid_deal_type_raises(self):
        with pytest.raises(ValidationError):
            DealCreate(name="Test", deal_type="invalid_type")

    def test_all_valid_deal_types(self):
        for dt in [
            "buyout", "growth_equity", "venture",
            "recapitalization", "add_on", "other",
            "m_and_a", "pe", "vc", "debt", "general",
        ]:
            deal = DealCreate(name="Test", deal_type=dt)
            assert deal.deal_type == dt

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            DealCreate()


class TestDealUpdate:
    def test_empty_update(self):
        update = DealUpdate()
        assert update.name is None
        assert update.description is None
        assert update.target_company is None
        assert update.deal_type is None
        assert update.stage is None
        assert update.status is None

    def test_partial_update(self):
        update = DealUpdate(name="Renamed", status="archived")
        assert update.name == "Renamed"
        assert update.status == "archived"

    def test_name_empty_raises(self):
        with pytest.raises(ValidationError):
            DealUpdate(name="")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            DealUpdate(name="x" * 256)

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            DealUpdate(status="deleted")

    def test_all_valid_statuses(self):
        for status in ["active", "closed", "archived"]:
            update = DealUpdate(status=status)
            assert update.status == status


class TestDealResponse:
    def test_valid(self):
        resp = DealResponse(
            id=UUID1,
            org_id=UUID2,
            name="Deal A",
            deal_type="pe",
            status="active",
            created_by=UUID3,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.org_id == UUID2
        assert resp.name == "Deal A"
        assert resp.deal_type == "pe"
        assert resp.status == "active"
        assert resp.description is None
        assert resp.target_company is None
        assert resp.stage is None

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DealResponse(
                id=UUID1,
                org_id=UUID2,
                name="Deal A",
                # missing deal_type, status, created_by, created_at, updated_at
            )


class TestDealMemberCreate:
    def test_valid_defaults(self):
        member = DealMemberCreate(user_id=UUID1)
        assert member.user_id == UUID1
        assert member.role == "analyst"

    def test_custom_role(self):
        member = DealMemberCreate(user_id=UUID1, role="lead")
        assert member.role == "lead"

    def test_all_valid_roles(self):
        for role in ["lead", "admin", "analyst", "viewer"]:
            member = DealMemberCreate(user_id=UUID1, role=role)
            assert member.role == role

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            DealMemberCreate(user_id=UUID1, role="superadmin")

    def test_missing_user_id_raises(self):
        with pytest.raises(ValidationError):
            DealMemberCreate()


class TestDealMemberResponse:
    def test_valid(self):
        resp = DealMemberResponse(user_id=UUID1, role="analyst", added_at=NOW)
        assert resp.user_id == UUID1
        assert resp.email is None
        assert resp.full_name is None
        assert resp.role == "analyst"
        assert resp.added_at == NOW

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DealMemberResponse(user_id=UUID1, added_at=NOW)  # missing role


# ═══════════════════════════════════════════════════════════════════════════════
# meeting.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMeetingCreate:
    def test_valid_defaults(self):
        meeting = MeetingCreate(title="Weekly Sync")
        assert meeting.title == "Weekly Sync"
        assert meeting.meeting_date is None
        assert meeting.source == "upload"

    def test_all_fields(self):
        meeting = MeetingCreate(title="Call", meeting_date=NOW, source="zoom")
        assert meeting.meeting_date == NOW
        assert meeting.source == "zoom"

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            MeetingCreate(title="")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError):
            MeetingCreate(title="x" * 501)

    def test_title_max_length_ok(self):
        meeting = MeetingCreate(title="x" * 500)
        assert len(meeting.title) == 500

    def test_invalid_source_raises(self):
        with pytest.raises(ValidationError):
            MeetingCreate(title="Test", source="google_meet")

    def test_all_valid_sources(self):
        for src in ["upload", "zoom", "teams", "bot", "slack"]:
            meeting = MeetingCreate(title="Test", source=src)
            assert meeting.source == src

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            MeetingCreate()


class TestMeetingUpdate:
    def test_empty_update(self):
        update = MeetingUpdate()
        assert update.title is None
        assert update.meeting_date is None

    def test_partial_update(self):
        update = MeetingUpdate(title="Renamed Meeting")
        assert update.title == "Renamed Meeting"

    def test_title_empty_raises(self):
        with pytest.raises(ValidationError):
            MeetingUpdate(title="")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError):
            MeetingUpdate(title="x" * 501)


class TestMeetingResponse:
    def test_valid(self):
        resp = MeetingResponse(
            id=UUID1,
            deal_id=UUID2,
            org_id=UUID3,
            title="Meeting",
            source="upload",
            status="completed",
            created_by=UUID1,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.title == "Meeting"
        assert resp.meeting_date is None
        assert resp.duration_seconds is None
        assert resp.error_message is None

    def test_all_optional_fields(self):
        resp = MeetingResponse(
            id=UUID1,
            deal_id=UUID2,
            org_id=UUID3,
            title="Meeting",
            meeting_date=NOW,
            duration_seconds=3600,
            source="zoom",
            status="failed",
            error_message="Transcription failed",
            created_by=UUID1,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.duration_seconds == 3600
        assert resp.error_message == "Transcription failed"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            MeetingResponse(
                id=UUID1, deal_id=UUID2, org_id=UUID3, title="Meeting"
                # missing source, status, created_by, created_at, updated_at
            )


class TestMeetingUploadResponse:
    def test_valid(self):
        resp = MeetingUploadResponse(
            meeting_id=UUID1,
            upload_url="https://s3.amazonaws.com/bucket/key",
            file_key="meetings/abc.wav",
        )
        assert resp.meeting_id == UUID1
        assert resp.upload_url == "https://s3.amazonaws.com/bucket/key"
        assert resp.file_key == "meetings/abc.wav"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            MeetingUploadResponse(meeting_id=UUID1)


class TestMeetingParticipantResponse:
    def test_valid(self):
        resp = MeetingParticipantResponse(id=UUID1, speaker_label="SPEAKER_00")
        assert resp.id == UUID1
        assert resp.speaker_label == "SPEAKER_00"
        assert resp.speaker_name is None
        assert resp.user_id is None

    def test_all_fields(self):
        resp = MeetingParticipantResponse(
            id=UUID1, speaker_label="SPEAKER_01", speaker_name="Alice", user_id=UUID2
        )
        assert resp.speaker_name == "Alice"
        assert resp.user_id == UUID2


class TestUpdateSpeakerName:
    def test_valid(self):
        update = UpdateSpeakerName(speaker_label="SPEAKER_00", speaker_name="Bob")
        assert update.speaker_label == "SPEAKER_00"
        assert update.speaker_name == "Bob"

    def test_missing_speaker_label_raises(self):
        with pytest.raises(ValidationError):
            UpdateSpeakerName(speaker_name="Bob")

    def test_missing_speaker_name_raises(self):
        with pytest.raises(ValidationError):
            UpdateSpeakerName(speaker_label="SPEAKER_00")


# ═══════════════════════════════════════════════════════════════════════════════
# transcript.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTranscriptResponse:
    def test_valid(self):
        resp = TranscriptResponse(
            id=UUID1,
            meeting_id=UUID2,
            full_text="Hello, this is the transcript.",
            language="en",
            word_count=6,
            created_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.full_text == "Hello, this is the transcript."
        assert resp.language == "en"
        assert resp.word_count == 6
        assert resp.confidence_score is None

    def test_with_confidence(self):
        resp = TranscriptResponse(
            id=UUID1,
            meeting_id=UUID2,
            full_text="Text",
            language="en",
            word_count=1,
            confidence_score=0.95,
            created_at=NOW,
        )
        assert resp.confidence_score == 0.95

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            TranscriptResponse(id=UUID1, meeting_id=UUID2, language="en", created_at=NOW)
            # missing full_text, word_count


class TestTranscriptSegmentResponse:
    def test_valid(self):
        resp = TranscriptSegmentResponse(
            id=UUID1,
            speaker_label="SPEAKER_00",
            text="Hello world",
            start_time=0.0,
            end_time=2.5,
            segment_index=0,
        )
        assert resp.speaker_label == "SPEAKER_00"
        assert resp.speaker_name is None
        assert resp.text == "Hello world"
        assert resp.start_time == 0.0
        assert resp.end_time == 2.5
        assert resp.confidence is None
        assert resp.segment_index == 0

    def test_all_fields(self):
        resp = TranscriptSegmentResponse(
            id=UUID1,
            speaker_label="SPEAKER_01",
            speaker_name="Alice",
            text="Good morning",
            start_time=2.5,
            end_time=5.0,
            confidence=0.99,
            segment_index=1,
        )
        assert resp.speaker_name == "Alice"
        assert resp.confidence == 0.99

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            TranscriptSegmentResponse(id=UUID1, speaker_label="SPEAKER_00")


# ═══════════════════════════════════════════════════════════════════════════════
# document.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentCreate:
    def test_valid(self):
        doc = DocumentCreate(title="Q3 Earnings", document_type="financial_statement")
        assert doc.title == "Q3 Earnings"
        assert doc.document_type == "financial_statement"

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            DocumentCreate(title="", document_type="report")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError):
            DocumentCreate(title="x" * 501, document_type="report")

    def test_title_max_length_ok(self):
        doc = DocumentCreate(title="x" * 500, document_type="report")
        assert len(doc.title) == 500

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            DocumentCreate(document_type="report")

    def test_missing_document_type_raises(self):
        with pytest.raises(ValidationError):
            DocumentCreate(title="Report")


class TestDocumentResponse:
    def test_valid(self):
        resp = DocumentResponse(
            id=UUID1,
            deal_id=UUID2,
            title="Report",
            document_type="financial",
            file_size=1024,
            uploaded_by=UUID3,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.file_size == 1024
        assert resp.document_type == "financial"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DocumentResponse(id=UUID1, deal_id=UUID2, title="Report")


class TestDocumentUploadResponse:
    def test_valid(self):
        resp = DocumentUploadResponse(
            document_id=UUID1,
            upload_url="https://s3.amazonaws.com/bucket/doc",
            file_key="docs/report.pdf",
        )
        assert resp.document_id == UUID1
        assert resp.upload_url == "https://s3.amazonaws.com/bucket/doc"
        assert resp.file_key == "docs/report.pdf"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DocumentUploadResponse(document_id=UUID1)


class TestDocumentDownloadResponse:
    def test_valid(self):
        resp = DocumentDownloadResponse(download_url="https://s3.amazonaws.com/bucket/doc")
        assert resp.download_url == "https://s3.amazonaws.com/bucket/doc"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DocumentDownloadResponse()


# ═══════════════════════════════════════════════════════════════════════════════
# analysis.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnalysisRequest:
    def test_default(self):
        req = AnalysisRequest()
        assert req.call_type == "general"

    def test_all_valid_call_types(self):
        valid_types = [
            "diligence",
            "management_presentation",
            "buyer_call",
            "financial_review",
            "qoe",
            "summarization",
            "general",
        ]
        for ct in valid_types:
            req = AnalysisRequest(call_type=ct)
            assert req.call_type == ct

    def test_invalid_call_type_raises(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(call_type="invalid_type")


class TestAnalysisResponse:
    def test_valid(self):
        resp = AnalysisResponse(
            id=UUID1,
            meeting_id=UUID2,
            call_type="diligence",
            model_used="claude-3-opus",
            prompt_version="1.0.0",
            status="completed",
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.call_type == "diligence"
        assert resp.structured_output is None
        assert resp.grounding_score is None
        assert resp.error_message is None
        assert resp.requested_by is None
        assert resp.version == 1

    def test_with_all_optional_fields(self):
        output = {"summary": "Great meeting", "risks": []}
        resp = AnalysisResponse(
            id=UUID1,
            meeting_id=UUID2,
            call_type="summarization",
            structured_output=output,
            model_used="claude-3-sonnet",
            prompt_version="2.0.0",
            grounding_score=0.85,
            status="completed",
            error_message=None,
            requested_by=UUID3,
            version=2,
            created_at=NOW,
            updated_at=NOW,
        )
        assert resp.structured_output == output
        assert resp.grounding_score == 0.85
        assert resp.requested_by == UUID3

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResponse(id=UUID1, meeting_id=UUID2, call_type="general")


# ═══════════════════════════════════════════════════════════════════════════════
# qa.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCitation:
    def test_valid(self):
        cit = Citation(
            source_type="transcript_segment",
            source_id=UUID1,
            text_excerpt="important quote",
        )
        assert cit.source_type == "transcript_segment"
        assert cit.source_id == UUID1
        assert cit.source_title is None
        assert cit.text_excerpt == "important quote"
        assert cit.timestamp is None
        assert cit.page is None

    def test_transcript_citation(self):
        cit = Citation(
            source_type="transcript_segment",
            source_id=UUID1,
            source_title="Meeting Transcript",
            text_excerpt="key point",
            timestamp=45.5,
        )
        assert cit.timestamp == 45.5

    def test_document_citation(self):
        cit = Citation(
            source_type="document_chunk",
            source_id=UUID1,
            source_title="Annual Report",
            text_excerpt="revenue grew 20%",
            page=15,
        )
        assert cit.page == 15

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            Citation(source_type="transcript_segment", source_id=UUID1)
            # missing text_excerpt


class TestQARequest:
    def test_valid(self):
        req = QARequest(question="What were the key risks discussed?")
        assert req.question == "What were the key risks discussed?"

    def test_empty_question_raises(self):
        with pytest.raises(ValidationError):
            QARequest(question="")

    def test_question_too_long_raises(self):
        with pytest.raises(ValidationError):
            QARequest(question="x" * 2001)

    def test_question_max_length_ok(self):
        req = QARequest(question="x" * 2000)
        assert len(req.question) == 2000

    def test_missing_question_raises(self):
        with pytest.raises(ValidationError):
            QARequest()


class TestQAResponse:
    def test_valid_minimal(self):
        resp = QAResponse(
            id=UUID1,
            deal_id=UUID2,
            question="What happened?",
            answer="They discussed revenue.",
            model_used="claude-3-opus",
            created_at=NOW,
        )
        assert resp.question == "What happened?"
        assert resp.answer == "They discussed revenue."
        assert resp.citations == []
        assert resp.grounding_score is None

    def test_with_citations(self):
        citation = Citation(
            source_type="transcript_segment",
            source_id=UUID3,
            text_excerpt="revenue grew by 20%",
        )
        resp = QAResponse(
            id=UUID1,
            deal_id=UUID2,
            question="Q?",
            answer="A.",
            citations=[citation],
            grounding_score=0.92,
            model_used="claude-3-opus",
            created_at=NOW,
        )
        assert len(resp.citations) == 1
        assert resp.citations[0].text_excerpt == "revenue grew by 20%"
        assert resp.grounding_score == 0.92

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            QAResponse(id=UUID1, deal_id=UUID2, question="Q?")


class TestQAHistoryResponse:
    def test_valid_minimal(self):
        resp = QAHistoryResponse(
            id=UUID1, question="Q?", answer="A.", created_at=NOW
        )
        assert resp.citations == []
        assert resp.grounding_score is None

    def test_with_all_fields(self):
        citation = Citation(
            source_type="document_chunk",
            source_id=UUID2,
            text_excerpt="excerpt",
            page=5,
        )
        resp = QAHistoryResponse(
            id=UUID1,
            question="Q?",
            answer="A.",
            citations=[citation],
            grounding_score=0.88,
            created_at=NOW,
        )
        assert len(resp.citations) == 1
        assert resp.grounding_score == 0.88

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            QAHistoryResponse(id=UUID1, question="Q?")


# ═══════════════════════════════════════════════════════════════════════════════
# integration.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegrationResponse:
    def test_valid(self):
        resp = IntegrationResponse(
            platform="zoom", is_active=True, connected_at=NOW
        )
        assert resp.platform == "zoom"
        assert resp.is_active is True
        assert resp.scopes is None
        assert resp.connected_at == NOW

    def test_with_scopes(self):
        resp = IntegrationResponse(
            platform="teams",
            is_active=False,
            scopes="read write",
            connected_at=NOW,
        )
        assert resp.scopes == "read write"
        assert resp.is_active is False

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            IntegrationResponse(platform="zoom")


class TestOAuthInitResponse:
    def test_valid(self):
        resp = OAuthInitResponse(authorization_url="https://zoom.us/oauth/authorize?client_id=abc")
        assert resp.authorization_url == "https://zoom.us/oauth/authorize?client_id=abc"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            OAuthInitResponse()


class TestBotSessionCreate:
    def test_valid(self):
        session = BotSessionCreate(
            meeting_url="https://zoom.us/j/123",
            platform="zoom",
            scheduled_start=NOW,
            deal_id=UUID1,
        )
        assert session.meeting_url == "https://zoom.us/j/123"
        assert session.platform == "zoom"
        assert session.scheduled_start == NOW
        assert session.deal_id == UUID1

    def test_teams_platform(self):
        session = BotSessionCreate(
            meeting_url="https://teams.microsoft.com/l/meetup-join/123",
            platform="teams",
            scheduled_start=NOW,
            deal_id=UUID1,
        )
        assert session.platform == "teams"

    def test_invalid_platform_raises(self):
        with pytest.raises(ValidationError):
            BotSessionCreate(
                meeting_url="https://meet.example.com/abc",
                platform="webex",
                scheduled_start=NOW,
                deal_id=UUID1,
            )

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            BotSessionCreate(meeting_url="https://zoom.us/j/123", platform="zoom")


class TestBotSessionResponse:
    def test_valid(self):
        resp = BotSessionResponse(
            id=UUID1,
            deal_id=UUID2,
            platform="zoom",
            meeting_url="https://zoom.us/j/123",
            status="active",
            consent_obtained=True,
            created_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.platform == "zoom"
        assert resp.status == "active"
        assert resp.consent_obtained is True
        assert resp.scheduled_start is None
        assert resp.actual_start is None
        assert resp.actual_end is None

    def test_all_optional_fields(self):
        resp = BotSessionResponse(
            id=UUID1,
            deal_id=UUID2,
            platform="teams",
            meeting_url="https://teams.microsoft.com/abc",
            status="completed",
            scheduled_start=NOW,
            actual_start=NOW,
            actual_end=NOW,
            consent_obtained=False,
            created_at=NOW,
        )
        assert resp.actual_start == NOW
        assert resp.actual_end == NOW

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            BotSessionResponse(id=UUID1, deal_id=UUID2, platform="zoom")


class TestWebhookResponse:
    def test_defaults(self):
        resp = WebhookResponse()
        assert resp.received is True

    def test_explicit_false(self):
        resp = WebhookResponse(received=False)
        assert resp.received is False


# ═══════════════════════════════════════════════════════════════════════════════
# audit.py tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditLogResponse:
    def test_valid(self):
        resp = AuditLogResponse(
            id=UUID1,
            org_id=UUID2,
            action="meeting.created",
            resource_type="meeting",
            created_at=NOW,
        )
        assert resp.id == UUID1
        assert resp.org_id == UUID2
        assert resp.user_id is None
        assert resp.deal_id is None
        assert resp.action == "meeting.created"
        assert resp.resource_type == "meeting"
        assert resp.resource_id is None
        assert resp.details is None
        assert resp.ip_address is None
        assert resp.created_at == NOW

    def test_all_fields(self):
        resp = AuditLogResponse(
            id=UUID1,
            org_id=UUID2,
            user_id=UUID3,
            deal_id=UUID1,
            action="deal.updated",
            resource_type="deal",
            resource_id=UUID2,
            details={"field": "status", "old": "active", "new": "closed"},
            ip_address="192.168.1.1",
            created_at=NOW,
        )
        assert resp.user_id == UUID3
        assert resp.deal_id == UUID1
        assert resp.resource_id == UUID2
        assert resp.details == {"field": "status", "old": "active", "new": "closed"}
        assert resp.ip_address == "192.168.1.1"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AuditLogResponse(id=UUID1, org_id=UUID2)


class TestAuditLogQuery:
    def test_empty_query(self):
        query = AuditLogQuery()
        assert query.user_id is None
        assert query.deal_id is None
        assert query.action is None
        assert query.resource_type is None
        assert query.start_date is None
        assert query.end_date is None

    def test_partial_query(self):
        query = AuditLogQuery(action="meeting.created", resource_type="meeting")
        assert query.action == "meeting.created"
        assert query.resource_type == "meeting"

    def test_full_query(self):
        query = AuditLogQuery(
            user_id=UUID1,
            deal_id=UUID2,
            action="deal.updated",
            resource_type="deal",
            start_date=NOW,
            end_date=NOW,
        )
        assert query.user_id == UUID1
        assert query.deal_id == UUID2
        assert query.start_date == NOW
        assert query.end_date == NOW


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-cutting / type coercion tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeCrossCutting:
    """Tests for type coercion and rejection across schemas."""

    def test_uuid_string_coercion(self):
        uid = uuid.uuid4()
        resp = IDResponse(id=str(uid))
        assert isinstance(resp.id, uuid.UUID)
        assert resp.id == uid

    def test_invalid_uuid_string(self):
        with pytest.raises(ValidationError):
            IDResponse(id="definitely-not-a-uuid")

    def test_integer_for_uuid_raises(self):
        with pytest.raises(ValidationError):
            IDResponse(id=12345)

    def test_datetime_string_coercion(self):
        user = UserResponse(
            id=UUID1,
            email="a@b.com",
            full_name="Test",
            created_at="2024-01-15T10:30:00Z",
        )
        assert isinstance(user.created_at, datetime)

    def test_invalid_datetime_string_raises(self):
        with pytest.raises(ValidationError):
            UserResponse(
                id=UUID1,
                email="a@b.com",
                full_name="Test",
                created_at="not-a-datetime",
            )

    def test_wrong_type_for_string_field(self):
        """Pydantic v2 coerces many types to string; list should fail."""
        with pytest.raises(ValidationError):
            ErrorResponse(code=["list", "not", "string"], message="test")

    def test_wrong_type_for_int_field(self):
        with pytest.raises(ValidationError):
            TranscriptSegmentResponse(
                id=UUID1,
                speaker_label="SPEAKER_00",
                text="Hello",
                start_time=0.0,
                end_time=1.0,
                segment_index="not-an-int",
            )

    def test_wrong_type_for_float_field(self):
        with pytest.raises(ValidationError):
            TranscriptSegmentResponse(
                id=UUID1,
                speaker_label="SPEAKER_00",
                text="Hello",
                start_time="not-a-float",
                end_time=1.0,
                segment_index=0,
            )

    def test_wrong_type_for_bool_field(self):
        """Pydantic v2 in strict mode would reject, but default mode coerces strings."""
        # Pydantic v2 in lax mode coerces "true"->True, but a random string should fail
        # Actually Pydantic v2 coerces many values. Let's test with a dict.
        with pytest.raises(ValidationError):
            WebhookResponse(received={"not": "a bool"})

    def test_nested_citation_in_qa_response(self):
        """Ensure nested model validation works."""
        with pytest.raises(ValidationError):
            QAResponse(
                id=UUID1,
                deal_id=UUID2,
                question="Q?",
                answer="A.",
                citations=[{"source_type": "transcript_segment"}],  # missing required fields
                model_used="claude",
                created_at=NOW,
            )

    def test_from_attributes_on_derived_schemas(self):
        """All schemas inheriting BaseSchema should have from_attributes=True."""
        schemas_to_check = [
            UserResponse, UserUpdate,
            OrgCreate, OrgUpdate, OrgResponse, OrgMemberResponse, OrgMemberCreate,
            DealCreate, DealUpdate, DealResponse, DealMemberCreate, DealMemberResponse,
            MeetingCreate, MeetingUpdate, MeetingResponse, MeetingUploadResponse,
            MeetingParticipantResponse, UpdateSpeakerName,
            TranscriptResponse, TranscriptSegmentResponse,
            DocumentCreate, DocumentResponse, DocumentUploadResponse, DocumentDownloadResponse,
            AnalysisRequest, AnalysisResponse,
            Citation, QARequest, QAResponse, QAHistoryResponse,
            IntegrationResponse, OAuthInitResponse,
            BotSessionCreate, BotSessionResponse, WebhookResponse,
            AuditLogResponse, AuditLogQuery,
        ]
        for schema in schemas_to_check:
            assert schema.model_config.get("from_attributes") is True, (
                f"{schema.__name__} should have from_attributes=True"
            )
