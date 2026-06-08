"""Unit tests for AnalysisService on the SQLite layer.

Covers the full run lifecycle: a running row is inserted, the LLM is called,
the JSON output is parsed and persisted, and the status resolves to
completed / partial / failed. Also pins per-(meeting, call_type) versioning
and newest-first listing.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest

from app.db.engine import (
    configure_engine,
    create_db_engine,
    get_session_factory,
)
from app.db.models import (
    Deal,
    Meeting,
    Organization,
    Profile,
    TranscriptSegment,
)
from app.db.schema import init_schema
from app.services.analysis_service import AnalysisService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, content: str, model: str = "fake/model-1") -> None:
        self.content = content
        self.model = model


class _FakeRouter:
    """Async ``complete`` returning a canned response, or raising."""

    def __init__(self, *, content: str | None = None, error: Exception | None = None):
        self._content = content
        self._error = error
        self.complete_calls: list[dict] = []

    async def complete(self, *, task_type, system_prompt, user_prompt, **kwargs):
        self.complete_calls.append(
            {"task_type": task_type, "user_prompt": user_prompt, **kwargs}
        )
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session(tmp_path):
    engine = create_db_engine(str(tmp_path / "test.db"))
    configure_engine(engine)
    init_schema(engine)
    s = get_session_factory()()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture()
def seeded(session):
    """Seed org / profile / deal / meeting + two finalized transcript segments."""
    org = Organization(name="Acme", slug="acme")
    user = Profile(email="user@example.com", full_name="User")
    session.add_all([org, user])
    session.flush()

    deal = Deal(org_id=org.id, name="Project Falcon", created_by=user.id)
    session.add(deal)
    session.flush()

    meeting = Meeting(
        org_id=org.id, deal_id=deal.id, title="Diligence Call", created_by=user.id
    )
    session.add(meeting)
    session.flush()

    session.add_all(
        [
            TranscriptSegment(
                meeting_id=meeting.id,
                speaker_label="spk_0",
                speaker_name="John",
                text="Revenue grew 15% to fifty million.",
                start_time=1.0,
                end_time=4.0,
                segment_index=0,
                is_partial=False,
            ),
            TranscriptSegment(
                meeting_id=meeting.id,
                speaker_label="spk_1",
                speaker_name="Mary",
                text="That's strong.",
                start_time=5.0,
                end_time=6.0,
                segment_index=1,
                is_partial=False,
            ),
            # A partial segment that must be excluded from the transcript text.
            TranscriptSegment(
                meeting_id=meeting.id,
                speaker_label="spk_0",
                speaker_name="John",
                text="ignore this partial",
                start_time=7.0,
                end_time=8.0,
                segment_index=2,
                is_partial=True,
            ),
        ]
    )
    session.flush()
    return {"org": org, "user": user, "deal": deal, "meeting": meeting}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_analysis_writes_completed_row_version_1(session, seeded):
    payload = {"summary": "Revenue up.", "findings": []}
    router = _FakeRouter(content=json.dumps(payload))
    svc = AnalysisService(session=session, llm_router=router)

    result = await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
        requested_by=UUID(seeded["user"].id),
    )

    assert result["status"] == "completed"
    assert result["version"] == 1
    assert result["structured_output"] == payload
    assert result["model_used"] == "fake/model-1"
    assert result["meeting_id"] == seeded["meeting"].id
    assert result["org_id"] == seeded["org"].id
    assert result["id"] is not None
    assert result["created_at"] is not None

    # The transcript fed to the LLM excludes the partial segment.
    assert len(router.complete_calls) == 1
    prompt = router.complete_calls[0]["user_prompt"]
    assert "John: Revenue grew 15% to fifty million." in prompt
    assert "Mary: That's strong." in prompt
    assert "ignore this partial" not in prompt


@pytest.mark.asyncio
async def test_second_run_increments_version(session, seeded):
    router = _FakeRouter(content=json.dumps({"ok": True}))
    svc = AnalysisService(session=session, llm_router=router)

    first = await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
    )
    second = await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
    )

    assert first["version"] == 1
    assert second["version"] == 2


@pytest.mark.asyncio
async def test_malformed_json_yields_partial(session, seeded):
    router = _FakeRouter(content="this is not json {")
    svc = AnalysisService(session=session, llm_router=router)

    result = await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
    )

    assert result["status"] == "partial"
    assert result["structured_output"]["parse_error"] is True
    assert result["structured_output"]["raw_output"] == "this is not json {"


@pytest.mark.asyncio
async def test_llm_error_yields_failed_and_reraises(session, seeded):
    router = _FakeRouter(error=RuntimeError("llm boom"))
    svc = AnalysisService(session=session, llm_router=router)

    with pytest.raises(RuntimeError, match="llm boom"):
        await svc.run_analysis(
            meeting_id=UUID(seeded["meeting"].id),
            org_id=UUID(seeded["org"].id),
            call_type="diligence",
        )

    # The running row was updated to failed with the error message persisted.
    rows = await svc.list_analyses(UUID(seeded["meeting"].id))
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_message"] == "llm boom"


@pytest.mark.asyncio
async def test_list_analyses_newest_first(session, seeded):
    router = _FakeRouter(content=json.dumps({"ok": True}))
    svc = AnalysisService(session=session, llm_router=router)

    await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
    )
    await svc.run_analysis(
        meeting_id=UUID(seeded["meeting"].id),
        org_id=UUID(seeded["org"].id),
        call_type="diligence",
    )

    rows = await svc.list_analyses(UUID(seeded["meeting"].id))
    versions = [r["version"] for r in rows]
    assert versions == sorted(versions, reverse=True)
    assert versions[0] == 2
