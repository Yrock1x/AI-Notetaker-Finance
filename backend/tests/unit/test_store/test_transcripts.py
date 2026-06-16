"""Tests for the transcripts store router — transcript, segments, participants,
chat. Covers ordering, partial exclusion, q/speaker filters, and cross-tenant
isolation (org B user gets 404 on every endpoint for an org A meeting)."""

from __future__ import annotations

from app.api.v1.store import transcripts
from app.db.engine import get_session_factory
from app.db.models import (
    Meeting,
    MeetingChatMessage,
    MeetingParticipant,
    Transcript,
    TranscriptSegment,
)

ROUTES = [("", transcripts.router)]


def _seed_meeting(seed):
    """Create a meeting in org A with transcript, segments, participants, chat."""
    session = get_session_factory()()
    try:
        meeting = Meeting(
            org_id=seed.org_a,
            deal_id=seed.deal_a,
            title="Kickoff",
            created_by=seed.user_a,
        )
        session.add(meeting)
        session.flush()
        mid = meeting.id

        session.add(
            Transcript(
                org_id=seed.org_a,
                meeting_id=mid,
                full_text="hello world full transcript",
                language="en",
                word_count=4,
                confidence_score=0.91,
                deepgram_response={"secret": "should-not-leak"},
            )
        )

        # out-of-order inserts to prove start_time ordering; one partial excluded
        session.add_all(
            [
                TranscriptSegment(
                    meeting_id=mid,
                    speaker_label="A",
                    speaker_name="Alice",
                    text="Second thing happened",
                    start_time=5.0,
                    end_time=7.0,
                    segment_index=1,
                    is_partial=False,
                ),
                TranscriptSegment(
                    meeting_id=mid,
                    speaker_label="B",
                    speaker_name="Bob",
                    text="First the apple fell",
                    start_time=1.0,
                    end_time=3.0,
                    segment_index=0,
                    is_partial=False,
                ),
                TranscriptSegment(
                    meeting_id=mid,
                    speaker_label="A",
                    speaker_name="Alice",
                    text="partial fragment should be hidden",
                    start_time=2.0,
                    end_time=2.5,
                    segment_index=99,
                    is_partial=True,
                ),
            ]
        )

        session.add_all(
            [
                MeetingParticipant(
                    meeting_id=mid,
                    speaker_label="A",
                    speaker_name="Alice",
                    email_address="alice@x.com",
                    joined_at="2026-06-07T10:00:00+00:00",
                ),
                MeetingParticipant(
                    meeting_id=mid,
                    speaker_label="B",
                    speaker_name="Bob",
                    email_address="bob@x.com",
                    joined_at="2026-06-07T10:01:00+00:00",
                ),
            ]
        )

        session.add_all(
            [
                MeetingChatMessage(
                    meeting_id=mid,
                    org_id=seed.org_a,
                    sender_name="Bob",
                    sender_email="bob@x.com",
                    text="later message",
                    sent_at="2026-06-07T10:05:00+00:00",
                ),
                MeetingChatMessage(
                    meeting_id=mid,
                    org_id=seed.org_a,
                    sender_name="Alice",
                    sender_email="alice@x.com",
                    text="earlier message",
                    sent_at="2026-06-07T10:02:00+00:00",
                ),
            ]
        )
        session.commit()
        return mid
    finally:
        session.close()


def test_get_transcript(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/meetings/{mid}/transcript")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_text"] == "hello world full transcript"
    assert body["word_count"] == 4
    assert body["confidence_score"] == 0.91
    assert "deepgram_response" not in body


def test_get_transcript_missing_404(make_client, seed):
    session = get_session_factory()()
    try:
        meeting = Meeting(
            org_id=seed.org_a, deal_id=seed.deal_a, title="No transcript", created_by=seed.user_a
        )
        session.add(meeting)
        session.commit()
        mid = meeting.id
    finally:
        session.close()
    client = make_client(ROUTES, seed.user_a)
    assert client.get(f"/meetings/{mid}/transcript").status_code == 404


def test_segments_ordered_and_partials_excluded(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/meetings/{mid}/transcript-segments")
    assert resp.status_code == 200, resp.text
    segs = resp.json()
    assert [s["start_time"] for s in segs] == [1.0, 5.0]  # ordered by start_time
    assert all(s["is_partial"] is False for s in segs)
    assert all("partial fragment" not in s["text"] for s in segs)


def test_segments_q_filter(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    segs = client.get(f"/meetings/{mid}/transcript-segments", params={"q": "APPLE"}).json()
    assert len(segs) == 1
    assert "apple" in segs[0]["text"].lower()


def test_segments_speaker_filter(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    segs = client.get(f"/meetings/{mid}/transcript-segments", params={"speaker": "A"}).json()
    # only the finalized A segment, partial A excluded
    assert len(segs) == 1
    assert segs[0]["speaker_label"] == "A"
    assert segs[0]["start_time"] == 5.0


def test_participants_listing(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    parts = client.get(f"/meetings/{mid}/participants").json()
    assert [p["speaker_label"] for p in parts] == ["A", "B"]  # by joined_at
    assert parts[0]["email_address"] == "alice@x.com"


def test_chat_listing(make_client, seed):
    mid = _seed_meeting(seed)
    client = make_client(ROUTES, seed.user_a)
    msgs = client.get(f"/meetings/{mid}/chat").json()
    assert [m["text"] for m in msgs] == ["earlier message", "later message"]  # by sent_at


def test_cross_tenant_all_endpoints_404(make_client, seed):
    mid = _seed_meeting(seed)  # org A meeting
    client = make_client(ROUTES, seed.user_b)  # outsider from org B
    assert client.get(f"/meetings/{mid}/transcript").status_code == 404
    assert client.get(f"/meetings/{mid}/transcript-segments").status_code == 404
    assert client.get(f"/meetings/{mid}/participants").status_code == 404
    assert client.get(f"/meetings/{mid}/chat").status_code == 404
