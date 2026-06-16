"""Server-Sent Events endpoint for live-meeting realtime updates.

Browsers subscribe to ``GET /meetings/{meeting_id}/stream`` and receive the
events the worker fans out via :mod:`app.realtime.pubsub` (transcript segments,
participants, chat, meeting + bot-session state changes). This replaces the
Supabase Realtime channel the live page used to subscribe to.

Tenant isolation: the meeting is scoped (``scoped_meeting_or_404``) *before* the
streaming response begins, so a cross-tenant request fails fast with 404 rather
than opening an empty stream.

Note: browser ``EventSource`` cannot send an Authorization header, so auth here
relies on the session cookie (``get_current_user`` reads it). The scope check
runs in a short-lived session that is closed before the stream opens, so the
open-ended generator holds no pooled DB connection.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.v1.store._common import scoped_meeting_or_404
from app.db.engine import get_session_factory
from app.db.scope import load_principal
from app.dependencies import AuthUser, get_current_user
from app.realtime.pubsub import meeting_topic, pubsub

router = APIRouter()

# Seconds between heartbeat comments; keeps proxies/load balancers from closing
# an otherwise idle connection.
HEARTBEAT_INTERVAL = 15.0


@router.get("/meetings/{meeting_id}/stream")
def stream_meeting(
    meeting_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> StreamingResponse:
    # Scope check in a SHORT-LIVED session that is closed before streaming
    # begins. The event generator below runs for the whole (potentially
    # hours-long) connection; holding a request-scoped get_db session would pin
    # a pooled DB connection for that entire lifetime, exhausting the shared
    # pool after a handful of concurrent live viewers and stalling every other
    # endpoint. A cross-tenant request still fails fast with 404 here, before
    # any stream opens.
    with get_session_factory()() as scope_session:
        principal = load_principal(scope_session, str(current_user.id))
        scoped_meeting_or_404(scope_session, principal, meeting_id)

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
                except TimeoutError:
                    # No event in the interval — send a heartbeat comment.
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            pubsub.unsubscribe(topic, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
