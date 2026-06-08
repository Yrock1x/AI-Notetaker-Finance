"""In-process async pub/sub for realtime fan-out.

Replaces Supabase Realtime for the single-instance FastAPI worker. The worker
now owns the live-meeting data (it ingests the Recall webhooks), so instead of
round-tripping changes through Postgres it publishes events directly to an
in-memory, per-topic set of subscriber queues. Each SSE connection holds one
queue; webhook handlers call :func:`publish_meeting_event` to fan an event out
to every connection watching that meeting.

Topics are strings; meeting topics use ``meeting:{meeting_id}``. This is stdlib
asyncio only — no external broker — which is sufficient because the worker runs
as a single process. If the worker is ever horizontally scaled this module is
the one place that must grow a real broker.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

__all__ = ["PubSub", "pubsub", "publish_meeting_event", "meeting_topic"]

# Bounded so a slow/stalled SSE consumer can't grow a queue without limit.
# On overflow we drop the event for that subscriber rather than block the
# publisher (which would stall the webhook ingest path for everyone).
DEFAULT_MAXSIZE = 1000


def meeting_topic(meeting_id: str) -> str:
    return f"meeting:{meeting_id}"


class PubSub:
    """An asyncio in-process pub/sub keyed by topic string."""

    def __init__(self, maxsize: int = DEFAULT_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, topic: str) -> asyncio.Queue:
        """Register and return a new queue that receives events for ``topic``."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[topic].add(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        """Remove ``queue`` from ``topic`` (no-op if already gone)."""
        subs = self._subscribers.get(topic)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(topic, None)

    async def publish(self, topic: str, event: dict) -> None:
        """Deliver ``event`` to every subscriber of ``topic``.

        Uses ``put_nowait`` and silently drops the event for any subscriber
        whose queue is full, so a single slow consumer never blocks the
        publisher or its peers.
        """
        for queue in tuple(self._subscribers.get(topic, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, ()))


# Module-level singleton shared by SSE endpoints and webhook handlers.
pubsub = PubSub()

# Allowed event kinds, mirroring the tables Supabase Realtime used to broadcast.
MEETING_EVENT_KINDS = frozenset(
    {"transcript_segment", "participant", "chat", "meeting", "bot_session"}
)


async def publish_meeting_event(meeting_id: str, kind: str, payload: dict) -> None:
    """Publish a ``{"kind", "payload"}`` event to a meeting's topic.

    ``kind`` is one of: transcript_segment, participant, chat, meeting,
    bot_session.
    """
    await pubsub.publish(meeting_topic(meeting_id), {"kind": kind, "payload": payload})
