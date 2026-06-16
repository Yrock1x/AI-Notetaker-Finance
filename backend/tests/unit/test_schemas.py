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

from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.common import (
    BaseSchema,
    CursorParams,
    ErrorResponse,
    IDResponse,
    PaginatedResponse,
    SuccessResponse,
)
from app.schemas.qa import Citation, QAHistoryResponse, QARequest, QAResponse

NOW = datetime.now(UTC)
UUID1 = uuid.uuid4()
UUID2 = uuid.uuid4()
UUID3 = uuid.uuid4()


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
