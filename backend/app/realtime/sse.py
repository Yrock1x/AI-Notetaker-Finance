"""Server-Sent Events endpoint for live-meeting realtime updates.

Browsers subscribe to ``GET /meetings/{meeting_id}/stream`` and receive the
events the worker fans out via :mod:`app.realtime.pubsub` (transcript segments,
participants, chat, meeting + bot-session state changes). This replaces the
Supabase Realtime channel the live page used to subscribe to.

Tenant isolation: the meeting is scoped (``scoped_meeting_or_404``) *before* the
streaming response begins, so a cross-tenant request fails fast with 404 rather
than opening an empty stream.

Note: browser ``EventSource`` cannot send an Authorization header, so cookie
auth will be wired up in a later workstream; for now the standard JWT
dependency is used.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_meeting_or_404
from app.db.scope import Principal
from app.realtime.pubsub import meeting_topic, pubsub

router = APIRouter()

# Seconds between heartbeat comments; keeps proxies/load balancers from closing
# an otherwise idle connection.
HEARTBEAT_INTERVAL = 15.0


@router.get("/meetings/{meeting_id}/stream")
def stream_meeting(
    meeting_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    # Scope check runs synchronously, before any streaming starts: a request for
    # a meeting outside the principal's org raises 404 here.
    scoped_meeting_or_404(session, principal, meeting_id)

    topic = meeting_topic(meeting_id)

    async def event_generator():
        queue = pubsub.subscribe(topic)
        try:
            # Initial comment flushes headers and confirms the stream is open.
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # No event in the interval — send a heartbeat comment.
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            pubsub.unsubscribe(topic, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
