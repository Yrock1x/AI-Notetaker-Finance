"""Pipeline-router tests against the SQLite + local-storage + sqlite-vec layer.

These exercise the migrated ``app/api/v1/internal.py`` handlers through a
``TestClient`` with ``get_db`` pointed at a throwaway SQLite engine and the
internal-token header set. External services (Deepgram / Recall / Fireworks)
are never called — embeddings come from a fake LLM router and storage is the
real local-disk store rooted under ``tmp_path``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import gen_uuid
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import (
    Deal,
    Document,
    Meeting,
    Organization,
    OrgMembership,
    Profile,
    TranscriptSegment,
)
from app.db.schema import init_schema
from app.db.vectors import match_embeddings_for_deal
from app.main import create_app
from app.storage import local as storage

INTERNAL_TOKEN = "test-internal-token"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeLLMRouter:
    """Returns a distinct unit vector per input so KNN matches are stable."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out: list[list[float]] = []
        for i, _ in enumerate(texts):
            v = [0.0] * 768
            v[i % 768] = 1.0
            out.append(v)
        return out


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def engine(tmp_path):
    eng = create_db_engine(str(tmp_path / "test.db"))
    configure_engine(eng)
    init_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    s = get_session_factory()()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _storage_and_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "worker_internal_token", INTERNAL_TOKEN)
    monkeypatch.setattr(settings, "storage_signing_key", "k")


@pytest.fixture()
def fake_llm(monkeypatch):
    router = FakeLLMRouter()
    monkeypatch.setattr("app.api.v1.internal.get_llm_router", lambda: router)
    return router


@pytest.fixture()
def client(engine):
    """TestClient whose get_db yields a session bound to the test engine."""
    app = create_app()

    def _override_get_db():
        session = get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    from app.db.engine import get_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": INTERNAL_TOKEN}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def _seed_org_user_deal(session, *, slug: str = "acme"):
    org = Organization(name=slug, slug=slug)
    user = Profile(email=f"{slug}@example.com", full_name=slug)
    session.add_all([org, user])
    session.flush()
    session.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
    deal = Deal(org_id=org.id, name=f"{slug} deal", created_by=user.id)
    session.add(deal)
    session.flush()
    return org, user, deal


def _seed_meeting(session, org, deal, user, **kw):
    m = Meeting(
        org_id=org.id,
        deal_id=deal.id,
        title=kw.pop("title", "Test meeting"),
        created_by=user.id,
        status=kw.pop("status", "uploaded"),
        **kw,
    )
    session.add(m)
    session.flush()
    return m


# ---------------------------------------------------------------------------
# embed_meeting
# ---------------------------------------------------------------------------
def test_embed_meeting_creates_embeddings_and_vectors(client, db, fake_llm):
    org, user, deal = _seed_org_user_deal(db)
    meeting = _seed_meeting(db, org, deal, user)
    for i in range(3):
        db.add(
            TranscriptSegment(
                meeting_id=meeting.id,
                speaker_label="Speaker 0",
                speaker_name="Alice",
                text=f"This is finalized segment number {i} with some words.",
                start_time=float(i),
                end_time=float(i) + 1.0,
                segment_index=i,
                is_partial=False,
            )
        )
    # A partial segment that must be ignored by the embed path.
    db.add(
        TranscriptSegment(
            meeting_id=meeting.id,
            speaker_label="Speaker 1",
            text="partial should be ignored",
            start_time=99.0,
            end_time=100.0,
            segment_index=99,
            is_partial=True,
        )
    )
    db.commit()

    resp = client.post(
        "/api/v1/internal/embed",
        json={"meeting_id": meeting.id},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] >= 1
    assert fake_llm.calls, "embed_batch should have been called"

    # The vec rows are searchable per-deal. Query the first chunk's vector.
    results = match_embeddings_for_deal(
        db,
        deal_id=deal.id,
        query_vector=[1.0 if i == 0 else 0.0 for i in range(768)],
        top_k=10,
        min_similarity=0.0,
    )
    assert results, "expected at least one embedding row + vec match"
    # No partial text should have been embedded.
    assert all("partial" not in r["chunk_text"] for r in results)


def test_embed_meeting_no_segments_returns_zero(client, db, fake_llm):
    org, user, deal = _seed_org_user_deal(db, slug="empty")
    meeting = _seed_meeting(db, org, deal, user)
    db.commit()

    resp = client.post(
        "/api/v1/internal/embed",
        json={"meeting_id": meeting.id},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 0


def test_embed_meeting_missing_token_rejected(client, db, fake_llm):
    org, user, deal = _seed_org_user_deal(db, slug="auth")
    meeting = _seed_meeting(db, org, deal, user)
    db.commit()
    resp = client.post(
        "/api/v1/internal/embed", json={"meeting_id": meeting.id}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# process_document
# ---------------------------------------------------------------------------
def test_process_document_extracts_text_and_embeds(client, db, fake_llm):
    org, user, deal = _seed_org_user_deal(db, slug="docs")
    file_key = f"{deal.id}/{gen_uuid()}.txt"
    doc = Document(
        org_id=org.id,
        deal_id=deal.id,
        title="Notes",
        document_type="txt",
        file_key=file_key,
        file_size=0,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()

    body = (
        "First paragraph of the deal memo with several words here.\n\n"
        "Second paragraph adding more context about the target company."
    )
    storage.save_bytes("deal-documents", file_key, body.encode("utf-8"))

    resp = client.post(
        "/api/v1/internal/process-document",
        json={"document_id": doc.id},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["embedding_count"] >= 1

    db.refresh(doc)
    assert doc.extracted_text and "First paragraph" in doc.extracted_text

    results = match_embeddings_for_deal(
        db,
        deal_id=deal.id,
        query_vector=[1.0 if i == 0 else 0.0 for i in range(768)],
        top_k=10,
        min_similarity=0.0,
    )
    assert results
    assert all(r["source_type"] == "document_chunk" for r in results)


def test_process_document_empty_file_sets_blank_text(client, db, fake_llm):
    org, user, deal = _seed_org_user_deal(db, slug="blank")
    file_key = f"{deal.id}/{gen_uuid()}.txt"
    doc = Document(
        org_id=org.id,
        deal_id=deal.id,
        title="Blank",
        document_type="txt",
        file_key=file_key,
        file_size=0,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    storage.save_bytes("deal-documents", file_key, b"   \n  ")

    resp = client.post(
        "/api/v1/internal/process-document",
        json={"document_id": doc.id},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["embedding_count"] == 0
    db.refresh(doc)
    assert doc.extracted_text == ""


# ---------------------------------------------------------------------------
# _dedupe_zoom_google_rows
# ---------------------------------------------------------------------------
def test_dedupe_collapses_google_shadow_into_zoom(db):
    from app.api.v1.internal import _dedupe_zoom_google_rows

    org, user, deal = _seed_org_user_deal(db, slug="dedupe")
    date = "2026-06-07T15:00:00+00:00"
    zoom = _seed_meeting(
        db,
        org,
        deal,
        user,
        title="Zoom row",
        meeting_date=date,
        source="zoom",
        external_provider="zoom",
        source_url="https://us05web.zoom.us/j/123456789",
        status="uploading",
    )
    # Google shadow of the same call: deal_id set by the user; bot opt-out.
    google = _seed_meeting(
        db,
        org,
        deal,
        user,
        title="Google shadow",
        meeting_date=date,
        source="meet",
        external_provider="google",
        source_url="https://calendar.google.com/event?id=abc",
        status="uploading",
    )
    # Wipe zoom's deal_id so we can confirm the merge copies it over.
    zoom.deal_id = None
    google.bot_enabled = False
    db.flush()

    _dedupe_zoom_google_rows(db, org.id, [date])
    db.commit()

    survivors = (
        db.query(Meeting).filter(Meeting.meeting_date == date).all()
    )
    assert len(survivors) == 1
    survivor = survivors[0]
    assert survivor.id == zoom.id
    assert survivor.source == "zoom"
    # User-set fields merged onto the surviving Zoom row.
    assert survivor.deal_id == deal.id
    assert survivor.bot_enabled is False
    # The google shadow row is gone.
    assert db.get(Meeting, google.id) is None


def test_dedupe_keeps_distinct_zoom_meetings(db):
    from app.api.v1.internal import _dedupe_zoom_google_rows

    org, user, deal = _seed_org_user_deal(db, slug="distinct")
    date = "2026-06-07T16:00:00+00:00"
    a = _seed_meeting(
        db, org, deal, user, title="Zoom A", meeting_date=date,
        source="zoom", external_provider="zoom",
        source_url="https://us05web.zoom.us/j/111", status="uploading",
    )
    b = _seed_meeting(
        db, org, deal, user, title="Meet B (different call)", meeting_date=date,
        source="meet", external_provider="google",
        source_url="https://us05web.zoom.us/j/222", status="uploading",
    )
    db.flush()

    _dedupe_zoom_google_rows(db, org.id, [date])
    db.commit()

    # Different zoom ids (111 vs 222) → both rows survive.
    assert db.get(Meeting, a.id) is not None
    assert db.get(Meeting, b.id) is not None
