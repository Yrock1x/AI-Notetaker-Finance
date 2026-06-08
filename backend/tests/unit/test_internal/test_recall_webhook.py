"""Recall live-transcription webhook tests against the SQLite Session layer.

These exercise the migrated ``app/api/v1/recall_webhooks.py`` handler through a
``TestClient`` with ``get_db`` pointed at a throwaway SQLite engine.

Signature handling: the webhook accepts unsigned payloads when
``settings.recall_webhook_secret`` is empty (the documented dev path in
``_verify_recall_signature``). We monkeypatch the secret to ``""`` so the full
HTTP path runs without having to compute a valid Svix/HMAC signature. Replay
protection keys off ``webhook-id``; we omit that header (or vary it) so the
in-process LRU never short-circuits a delivery we want handled.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import (
    Deal,
    Meeting,
    MeetingBotSession,
    MeetingChatMessage,
    MeetingParticipant,
    Organization,
    OrgMembership,
    Profile,
    TranscriptSegment,
)
from app.db.schema import init_schema
from app.main import create_app

BOT_ID = "recall-bot-123"


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
def _unsigned_webhooks(monkeypatch):
    # Empty secret → _verify_recall_signature accepts unsigned payloads.
    monkeypatch.setattr(settings, "recall_webhook_secret", "")


@pytest.fixture()
def client(engine):
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def _seed(session):
    org = Organization(name="acme", slug="acme")
    user = Profile(email="acme@example.com", full_name="acme")
    session.add_all([org, user])
    session.flush()
    session.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
    deal = Deal(org_id=org.id, name="acme deal", created_by=user.id)
    session.add(deal)
    session.flush()
    meeting = Meeting(
        org_id=org.id,
        deal_id=deal.id,
        title="Live meeting",
        created_by=user.id,
        status="scheduled",
    )
    session.add(meeting)
    session.flush()
    bot = MeetingBotSession(
        org_id=org.id,
        deal_id=deal.id,
        meeting_id=meeting.id,
        platform="zoom",
        meeting_url="https://zoom.us/j/1",
        status="recording",
        recall_bot_id=BOT_ID,
        created_by=user.id,
    )
    session.add(bot)
    session.flush()
    return org, user, deal, meeting, bot


WEBHOOK_URL = "/api/v1/webhooks/recall"


# ---------------------------------------------------------------------------
# Transcript upsert: partial → final collapses in place
# ---------------------------------------------------------------------------
def test_transcript_partial_then_final_upserts_in_place(client, db):
    _seed(db)
    db.commit()

    segment = {"id": "seg-1", "speaker": "Alice", "text": "hello", "index": 0}
    partial = {
        "event": "transcript.partial_data",
        "data": {"bot_id": BOT_ID, "segment": dict(segment)},
    }
    resp = client.post(WEBHOOK_URL, json=partial)
    assert resp.status_code == 200, resp.text
    assert resp.json()["handled"] is True
    assert resp.json()["is_partial"] is True

    rows = db.query(TranscriptSegment).filter_by(recall_segment_id="seg-1").all()
    assert len(rows) == 1
    assert rows[0].is_partial is True
    assert rows[0].text == "hello"

    # Final delivery with the SAME recall_segment_id — must update in place.
    final_seg = {"id": "seg-1", "speaker": "Alice", "text": "hello world", "index": 0}
    final = {"event": "transcript.data", "data": {"bot_id": BOT_ID, "segment": final_seg}}
    resp = client.post(WEBHOOK_URL, json=final)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_partial"] is False

    db.expire_all()
    rows = db.query(TranscriptSegment).filter_by(recall_segment_id="seg-1").all()
    assert len(rows) == 1, "partial → final must collapse to ONE row"
    assert rows[0].is_partial is False
    assert rows[0].text == "hello world"


def test_transcript_unknown_bot_is_acked(client, db):
    _seed(db)
    db.commit()
    resp = client.post(
        WEBHOOK_URL,
        json={
            "event": "transcript.data",
            "data": {"bot_id": "nope", "segment": {"id": "x", "text": "hi"}},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["reason"] == "unknown_bot"
    assert db.query(TranscriptSegment).count() == 0


# ---------------------------------------------------------------------------
# Participant upsert + idempotency
# ---------------------------------------------------------------------------
def test_participant_upsert_and_idempotent(client, db):
    _, _, _, meeting, _ = _seed(db)
    db.commit()

    body = {
        "event": "participant_events.join",
        "data": {
            "bot_id": BOT_ID,
            "data": {
                "participant": {"id": "p1", "name": "Bob", "email": "bob@x.com"},
                "timestamp": "2026-06-07T15:00:00+00:00",
            },
        },
    }
    resp = client.post(WEBHOOK_URL, json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["handled"] is True

    rows = db.query(MeetingParticipant).filter_by(meeting_id=meeting.id).all()
    assert len(rows) == 1
    assert rows[0].speaker_name == "Bob"
    assert rows[0].joined_at == "2026-06-07T15:00:00+00:00"

    # Repeat delivery for the same participant — update in place, no dup.
    leave = {
        "event": "participant_events.leave",
        "data": {
            "bot_id": BOT_ID,
            "data": {
                "participant": {"id": "p1", "name": "Bob"},
                "timestamp": "2026-06-07T15:30:00+00:00",
            },
        },
    }
    resp = client.post(WEBHOOK_URL, json=leave)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    rows = db.query(MeetingParticipant).filter_by(meeting_id=meeting.id).all()
    assert len(rows) == 1, "same recall_participant_id must not duplicate"
    assert rows[0].left_at == "2026-06-07T15:30:00+00:00"


# ---------------------------------------------------------------------------
# Chat insert + idempotency on replay
# ---------------------------------------------------------------------------
def test_chat_insert_and_idempotent(client, db):
    _, _, _, meeting, _ = _seed(db)
    db.commit()

    body = {
        "event": "chat_messages.create",
        "data": {
            "bot_id": BOT_ID,
            "data": {
                "message": {
                    "id": "m1",
                    "text": "hi all",
                    "sender": {"name": "Carol", "email": "carol@x.com"},
                    "timestamp": "2026-06-07T15:05:00+00:00",
                }
            },
        },
    }
    resp = client.post(WEBHOOK_URL, json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["handled"] is True

    rows = db.query(MeetingChatMessage).filter_by(meeting_id=meeting.id).all()
    assert len(rows) == 1
    assert rows[0].text == "hi all"
    assert rows[0].sender_name == "Carol"

    # Re-deliver the identical message (same recall_message_id) — no dup row.
    resp = client.post(WEBHOOK_URL, json=body)
    assert resp.status_code == 200, resp.text
    db.expire_all()
    rows = db.query(MeetingChatMessage).filter_by(meeting_id=meeting.id).all()
    assert len(rows) == 1, "same recall_message_id must not duplicate"


# ---------------------------------------------------------------------------
# Status change updates the bot session (and meeting) status
# ---------------------------------------------------------------------------
def test_status_change_updates_session_and_meeting(client, db):
    _, _, _, meeting, bot = _seed(db)
    bot.status = "joining"
    meeting.status = "scheduled"
    db.commit()

    resp = client.post(
        WEBHOOK_URL,
        json={"event": "bot.in_call_recording", "data": {"bot_id": BOT_ID}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["next_status"] == "recording"

    db.expire_all()
    assert db.get(MeetingBotSession, bot.id).status == "recording"
    assert db.get(Meeting, meeting.id).status == "recording"
