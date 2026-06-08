"""Tests for the in-process realtime pub/sub and the SSE scope check."""

from __future__ import annotations

import asyncio

import pytest

from app.realtime import sse
from app.realtime.pubsub import (
    PubSub,
    meeting_topic,
    publish_meeting_event,
    pubsub,
)


async def test_publish_delivers_to_subscriber():
    ps = PubSub()
    q = ps.subscribe("t1")
    await ps.publish("t1", {"hello": "world"})
    assert q.get_nowait() == {"hello": "world"}


async def test_multiple_subscribers_same_topic_both_receive():
    ps = PubSub()
    q1 = ps.subscribe("t1")
    q2 = ps.subscribe("t1")
    await ps.publish("t1", {"n": 1})
    assert q1.get_nowait() == {"n": 1}
    assert q2.get_nowait() == {"n": 1}


async def test_other_topic_does_not_receive():
    ps = PubSub()
    q_a = ps.subscribe("a")
    q_b = ps.subscribe("b")
    await ps.publish("a", {"only": "a"})
    assert q_a.get_nowait() == {"only": "a"}
    assert q_b.empty()


async def test_unsubscribe_stops_delivery():
    ps = PubSub()
    q = ps.subscribe("t1")
    ps.unsubscribe("t1", q)
    await ps.publish("t1", {"x": 1})
    assert q.empty()
    assert ps.subscriber_count("t1") == 0


async def test_unsubscribe_unknown_is_noop():
    ps = PubSub()
    # Should not raise even though nothing was ever subscribed.
    ps.unsubscribe("nope", asyncio.Queue())


async def test_full_queue_drops_without_blocking():
    ps = PubSub(maxsize=1)
    q = ps.subscribe("t1")
    await ps.publish("t1", {"i": 0})  # fills the queue
    await ps.publish("t1", {"i": 1})  # dropped, must not block
    assert q.get_nowait() == {"i": 0}
    assert q.empty()


async def test_publish_meeting_event_wraps_kind_and_payload():
    mid = "meeting-123"
    q = pubsub.subscribe(meeting_topic(mid))
    try:
        await publish_meeting_event(mid, "transcript_segment", {"text": "hi"})
        assert q.get_nowait() == {
            "kind": "transcript_segment",
            "payload": {"text": "hi"},
        }
    finally:
        pubsub.unsubscribe(meeting_topic(mid), q)


def _seed_meeting_in_org_a(seed):
    from app.db.engine import get_session_factory
    from app.db.models import Meeting

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
        session.commit()
        return mid
    finally:
        session.close()


def test_stream_cross_tenant_returns_404(make_client, seed):
    """A user in org B requesting an org A meeting's stream gets 404 fast.

    The scope check runs before streaming begins, so the request returns
    promptly instead of hanging on the infinite generator.
    """
    mid = _seed_meeting_in_org_a(seed)
    client = make_client([("", sse.router)], seed.user_b)
    resp = client.get(f"/meetings/{mid}/stream")
    assert resp.status_code == 404
