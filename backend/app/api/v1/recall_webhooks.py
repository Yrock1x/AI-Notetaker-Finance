"""Recall.ai webhook — single endpoint that handles both real-time
transcript events and bot lifecycle events.

Transcript events (``transcript.partial`` / ``transcript.final``) upsert
into ``transcript_segments`` keyed on ``recall_segment_id`` so partials get
replaced in place by their finalized text. The worker's in-process pub/sub
(``publish_meeting_event``) broadcasts each change to the Live panel's SSE
stream.

Lifecycle events (``bot.status_change``) flip ``meeting_bot_sessions.status``
and, when the call ends, fire ``meeting/uploaded`` into Inngest so the
post-meeting pipeline (embed + analyze) kicks off automatically.

Configure one webhook URL in the Recall.ai dashboard that points here —
every event type lands on this handler.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import logging
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.db.models import (
    Meeting,
    MeetingBotSession,
    MeetingChatMessage,
    MeetingParticipant,
    TranscriptSegment,
)
from app.integrations.inngest import send_event
from app.realtime.pubsub import publish_meeting_event

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Replay protection
#
# Recall's signature window is set by ``webhook-timestamp``; without dedupe,
# a captured webhook can be re-played within that window. Cache recently
# observed message-ids and return early on repeats. Bounded LRU so memory
# is constant. Single-process scope is fine for the worker today; if we
# scale horizontally, swap this for a Redis/Postgres-backed dedupe.
# ---------------------------------------------------------------------------
_SEEN_WEBHOOK_IDS: OrderedDict[str, float] = OrderedDict()
_SEEN_MAX_SIZE = 10000
_SEEN_TTL_SECONDS = 600  # 10 min — covers both Recall's 5-min ts tolerance

# Reject Svix-signed webhooks whose timestamp is too far from now. This bounds
# the replay window even after the in-process dedup LRU is cleared (e.g. a
# deploy/restart), mirroring the Zoom/Slack handlers in webhooks.py.
_RECALL_TIMESTAMP_TOLERANCE = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Backpressure on the live-ingest write path
#
# Each transcript partial upserts a row into the worker-owned SQLite DB;
# writes serialize there, and at burst — 50 concurrent live meetings stacking
# partials — uncapped concurrency can starve other request types. Cap
# concurrent writes per worker process; once full, new webhook handlers wait,
# which gives Recall natural backpressure rather than letting us amplify the
# spike. 8 keeps healthy headroom while still serving steady-state load.
# ---------------------------------------------------------------------------
_WRITE_SEMAPHORE = asyncio.Semaphore(8)


def _is_replay(msg_id: str | None) -> bool:
    if not msg_id:
        return False
    now = time.time()
    # Evict expired entries from the head of the LRU.
    while _SEEN_WEBHOOK_IDS:
        oldest_id, oldest_ts = next(iter(_SEEN_WEBHOOK_IDS.items()))
        if now - oldest_ts > _SEEN_TTL_SECONDS:
            _SEEN_WEBHOOK_IDS.popitem(last=False)
        else:
            break
    if msg_id in _SEEN_WEBHOOK_IDS:
        return True
    if len(_SEEN_WEBHOOK_IDS) >= _SEEN_MAX_SIZE:
        _SEEN_WEBHOOK_IDS.popitem(last=False)
    _SEEN_WEBHOOK_IDS[msg_id] = now
    return False


# ---------------------------------------------------------------------------
# Signature verification
#
# Recall pushes webhooks from two different systems:
#
# 1. Account-level dashboard webhooks are signed to the Standard Webhooks
#    spec (https://www.standardwebhooks.com/), which Svix uses underneath.
#    Recall's dashboard sends the generic ``webhook-id`` / ``webhook-timestamp``
#    / ``webhook-signature`` header names — not the Svix-branded ``svix-*``
#    variant. Signature format is ``v1,<base64_hmac>`` (optionally multiple
#    space-separated). The secret shown in the dashboard is URL-safe base64
#    (prefixed ``whsec_`` before we strip it into RECALL_WEBHOOK_SECRET).
#    Accept either header set.
#
# 2. Older per-bot realtime_endpoints use a plain ``x-recall-signature``
#    header carrying a hex-encoded HMAC-SHA256 of the raw body.
#
# Accept both so the one env var works for everything Recall might send.
# ---------------------------------------------------------------------------
def _secret_bytes() -> bytes:
    raw = settings.recall_webhook_secret
    if raw.startswith("whsec_"):
        raw = raw[len("whsec_") :]
    # URL-safe base64, may be missing padding.
    padded = raw + "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except Exception:
        return settings.recall_webhook_secret.encode()


def _verify_svix(
    raw_body: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    signed = f"{svix_id}.{svix_timestamp}.".encode() + raw_body
    expected = base64.b64encode(
        hmac.new(_secret_bytes(), signed, hashlib.sha256).digest()
    ).decode()
    # Header is one or more space-separated "<version>,<sig>" pairs.
    for part in svix_signature.split(" "):
        _, _, sig = part.partition(",")
        if sig and hmac.compare_digest(expected, sig):
            return True
    return False


def _verify_recall_signature(
    raw_body: bytes,
    *,
    x_recall_signature: str | None,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
) -> None:
    if not settings.recall_webhook_secret:
        # In dev we accept unsigned webhooks to simplify local testing.
        return

    if svix_id and svix_timestamp and svix_signature:
        # Freshness check first: a captured-but-stale signed webhook is rejected
        # even if its signature still validates.
        try:
            skew = abs(time.time() - int(svix_timestamp))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Recall webhook timestamp",
            ) from None
        if skew > _RECALL_TIMESTAMP_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Recall webhook timestamp expired",
            )
        if _verify_svix(raw_body, svix_id, svix_timestamp, svix_signature):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Svix signature",
        )

    if x_recall_signature:
        expected = hmac.new(
            settings.recall_webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, x_recall_signature):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Recall signature",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Recall signature header",
    )


# ---------------------------------------------------------------------------
# Shared: look up the bot session row for a bot_id
# ---------------------------------------------------------------------------
def _session_for_bot(session: Session, bot_id: str) -> MeetingBotSession | None:
    if not bot_id:
        return None
    return session.scalar(
        select(MeetingBotSession)
        .where(MeetingBotSession.recall_bot_id == bot_id)
        .limit(1)
    )


# ---------------------------------------------------------------------------
# Endpoint: unified handler
# ---------------------------------------------------------------------------
@router.post("")
@router.post("/transcript")  # kept for back-compat if old URLs are still in Recall
async def recall_webhook(
    request: Request,
    x_recall_signature: str | None = Header(default=None),
    svix_id: str | None = Header(default=None),
    svix_timestamp: str | None = Header(default=None),
    svix_signature: str | None = Header(default=None),
    webhook_id: str | None = Header(default=None),
    webhook_timestamp: str | None = Header(default=None),
    webhook_signature: str | None = Header(default=None),
    session: Session = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    # Recall's dashboard uses the Standard Webhooks ``webhook-*`` header
    # names; realtime_endpoints may use ``svix-*``. Collapse both into one
    # triple before verifying.
    msg_id = svix_id or webhook_id
    msg_ts = svix_timestamp or webhook_timestamp
    msg_sig = svix_signature or webhook_signature
    logger.info(
        "recall_webhook_received bytes=%d msg_id=%s has_std_sig=%s has_x_recall_sig=%s",
        len(raw_body),
        msg_id or "-",
        bool(msg_sig),
        bool(x_recall_signature),
    )
    _verify_recall_signature(
        raw_body,
        x_recall_signature=x_recall_signature,
        svix_id=msg_id,
        svix_timestamp=msg_ts,
        svix_signature=msg_sig,
    )

    # Reject replays of dashboard-signed webhooks (which carry a unique
    # ``webhook-id``). Returning 200 prevents Recall from retrying. Legacy
    # ``x-recall-signature`` events have no message-id; those rely on the
    # idempotent UPSERTs further down (transcript_segments by
    # recall_segment_id, etc.) so a re-played one is effectively a no-op.
    if _is_replay(msg_id):
        logger.warning("recall_webhook_replay_blocked msg_id=%s", msg_id)
        return {"received": True, "handled": False, "reason": "replay"}

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        ) from exc

    event = payload.get("event", "")
    data = payload.get("data", {}) or {}

    # --- Transcript events ---------------------------------------------------
    # realtime_endpoints spells these ``transcript.partial_data`` /
    # ``transcript.data``. The dashboard also fires resource-lifecycle events
    # (``transcript.processing`` / ``transcript.done``) when post-call
    # processing completes — we just ACK those; the real work happens on
    # ``bot.done`` via /internal/bot/finalize.
    if event in ("transcript.data", "transcript.partial_data"):
        return await _handle_transcript(event, data, session)
    if event.startswith("transcript."):
        return {"received": True, "handled": False, "event": event}

    # --- Bot lifecycle -------------------------------------------------------
    # Dashboard fires flat event names (``bot.joining_call``,
    # ``bot.in_call_recording``, ``bot.done``, ``bot.fatal`` …); realtime
    # endpoints, if ever configured, use ``bot.status_change`` with a nested
    # ``data.status.code``. Both end up in _handle_status_change.
    if event.startswith("bot."):
        return await _handle_status_change(event, data, session)

    # --- Participant join / leave -------------------------------------------
    if event.startswith(("participant_events.", "participant.")):
        return await _handle_participant(event, data, session)

    # --- In-meeting chat -----------------------------------------------------
    if event.startswith(("chat_messages.", "chat.")):
        return await _handle_chat(event, data, session)

    # ``recording.done`` / ``meeting_metadata.done`` / ``video_mixed.done``
    # etc. — just ACK. /internal/bot/finalize pulls whatever media shortcuts
    # are ready at the time it runs (triggered by bot.done above).
    logger.info("recall_webhook_unhandled event=%s", event)
    return {"received": True, "handled": False, "event": event}


async def _handle_transcript(
    event: str, data: dict, session: Session
) -> dict:
    # Recall sends transcript events in two very different shapes:
    #  1. Legacy per-bot push: {"event":"transcript.partial", "data":
    #     {"bot_id":"…", "segment":{"id","speaker","text","start_time",…}}}
    #  2. realtime_endpoints push: {"event":"transcript.partial_data", "data":
    #     {"bot":{"id","metadata"}, "data":{"participant":{…},"words":[…]}}}
    # Normalise both into the same row before upsert so the DB stays uniform.
    is_partial = event.endswith((".partial", ".partial_data"))

    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    # Realtime payloads nest the body under data.data
    inner = data.get("data") if isinstance(data.get("data"), dict) else None
    segment = data.get("segment") or {}

    bot_session = _session_for_bot(session, bot_id)
    if not bot_session:
        logger.warning("recall_webhook_unknown_bot bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "unknown_bot"}
    meeting_id = bot_session.meeting_id
    if not meeting_id:
        logger.warning("recall_webhook_no_meeting bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "no_meeting"}

    if inner:
        words = inner.get("words") or []
        if not words:
            return {"received": True, "handled": False, "reason": "empty_words"}
        participant = inner.get("participant") or {}
        text = " ".join((w.get("text") or "").strip() for w in words if w.get("text"))
        first = (words[0].get("start_timestamp") or {}).get("relative") or 0.0
        last = (words[-1].get("end_timestamp") or {}).get("relative") or first
        # Realtime payload has no stable segment id; build a deterministic one
        # so partial → final upserts collapse in place.
        segment_id = (
            f"{bot_id}:{participant.get('id','?')}:{float(first):.3f}"
        )
        row = {
            "meeting_id": meeting_id,
            "recall_segment_id": segment_id,
            "speaker_label": participant.get("name") or "Speaker",
            "speaker_name": participant.get("name"),
            "text": text,
            "start_time": float(first),
            "end_time": float(last),
            "confidence": None,
            "segment_index": 0,
            "is_partial": is_partial,
        }
    else:
        recall_segment_id = segment.get("id")
        if not recall_segment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Segment missing id",
            )
        row = {
            "meeting_id": meeting_id,
            "recall_segment_id": recall_segment_id,
            "speaker_label": segment.get("speaker") or "Speaker",
            "text": segment.get("text") or "",
            "start_time": float(segment.get("start_time") or 0),
            "end_time": float(segment.get("end_time") or 0),
            "confidence": segment.get("confidence"),
            "segment_index": int(segment.get("index") or 0),
            "is_partial": is_partial,
        }

    async with _WRITE_SEMAPHORE:
        # UPSERT keyed on recall_segment_id so a partial gets replaced in
        # place by its finalized text instead of inserting a new row.
        existing = session.scalar(
            select(TranscriptSegment).where(
                TranscriptSegment.recall_segment_id == row["recall_segment_id"]
            )
        )
        if existing is not None:
            for key, value in row.items():
                setattr(existing, key, value)
        else:
            session.add(TranscriptSegment(**row))
        session.flush()

    # Broadcast to the worker's in-process pub/sub so the new SSE stream
    # delivers live segments. Never let a pub/sub hiccup fail the webhook.
    with contextlib.suppress(Exception):
        await publish_meeting_event(meeting_id, "transcript_segment", row)

    return {"received": True, "handled": True, "is_partial": is_partial}


async def _handle_status_change(
    event: str, data: dict, session: Session
) -> dict:
    """Bot lifecycle handoff.

    Maps Recall's ``code`` field (from ``data.status``) to our
    ``meeting_bot_sessions.status`` values. When the call truly ends
    (``call_ended`` / ``done``), we fire ``meeting/bot-completed`` so the
    bot-specific Inngest pipeline (pull transcript + participants from
    Recall, then embed + analyze) runs.
    """
    # Dashboard payloads look like:
    #   {"event":"bot.joining_call", "data":{"bot":{"id",…},"data":{…}}}
    # Realtime-endpoints payloads:
    #   {"event":"bot.status_change","data":{"bot":{…},"data":{"code",…}}}
    # Legacy payloads:
    #   {"event":"bot.done","data":{"bot_id":"…","status":{"code":"…"}}}
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    inner = data.get("data") if isinstance(data.get("data"), dict) else None
    # For dashboard events the status IS the event suffix — no nested code.
    event_suffix = event.split(".", 1)[1] if "." in event else ""
    recall_status = (
        (inner or {}).get("code")
        or (data.get("status") or {}).get("code")
        or event_suffix
    )

    bot_session = _session_for_bot(session, bot_id)
    if not bot_session:
        logger.warning("recall_status_unknown_bot bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "unknown_bot"}

    # Map Recall status → our session status
    status_map: dict[str, str] = {
        "ready": "scheduled",
        "joining_call": "joining",
        "in_waiting_room": "joining",
        "in_call_not_recording": "joining",
        "in_call_recording": "recording",
        "recording_permission_allowed": "recording",
        "call_ended": "completed",
        "done": "completed",
        "fatal": "failed",
    }
    next_status = status_map.get(recall_status)
    if next_status is None and event in ("bot.call_ended", "bot.done"):
        next_status = "completed"

    if next_status is None:
        logger.info(
            "recall_status_no_map bot_id=%s recall_status=%s", bot_id, recall_status
        )
        return {"received": True, "handled": False, "recall_status": recall_status}

    # Only set a real timestamp from Recall; otherwise leave the column for
    # the row's own ``updated_at`` default rather than writing a literal.
    real_ts = data.get("updated_at")
    async with _WRITE_SEMAPHORE:
        bot_session.status = next_status
        if next_status == "recording" and real_ts:
            bot_session.actual_start = real_ts
        elif next_status in ("completed", "failed") and real_ts:
            bot_session.actual_end = real_ts
        session.flush()

    meeting_id = bot_session.meeting_id
    if meeting_id:
        with contextlib.suppress(Exception):
            await publish_meeting_event(
                meeting_id,
                "bot_session",
                {
                    "id": bot_session.id,
                    "meeting_id": meeting_id,
                    "deal_id": bot_session.deal_id,
                    "status": next_status,
                },
            )

    # Keep meetings.status in sync with the bot's real lifecycle. bot_start
    # intentionally leaves the meeting at 'scheduled' until Recall confirms
    # the bot is in-call, so the Live tab's "waiting" state is truthful.
    if next_status == "recording" and meeting_id:
        async with _WRITE_SEMAPHORE:
            meeting = session.get(Meeting, meeting_id)
            if meeting is not None:
                meeting.status = "recording"
                session.flush()
        with contextlib.suppress(Exception):
            await publish_meeting_event(
                meeting_id, "meeting", {"id": meeting_id, "status": "recording"}
            )
    elif next_status == "completed" and meeting_id:
        # Bot meetings take a dedicated pipeline that pulls the authoritative
        # transcript + participants from Recall's recording shortcuts —
        # Deepgram already ran during the call, so the file-upload path
        # (``meeting/uploaded``) doesn't apply. The finalize step flips
        # meetings.status to 'uploaded' itself once the pull succeeds.
        # Commit the status write before the Inngest send so the SQLite writer
        # lock isn't held across that network call (this is the hot live path).
        # Committing first also means the status persists even if the send fails
        # and Recall retries the webhook.
        session.commit()
        await send_event(
            "meeting/bot-completed",
            {
                "session_id": bot_session.id,
                "meeting_id": meeting_id,
                "deal_id": bot_session.deal_id or "",
            },
        )

    return {
        "received": True,
        "handled": True,
        "next_status": next_status,
        "recall_status": recall_status,
    }


async def _handle_participant(
    event: str, data: dict, session: Session
) -> dict:
    """Upsert ``meeting_participants`` from Recall participant_events.*.

    Accepts both the legacy shape and the realtime_endpoints shape:
      legacy:   { bot_id, participant: {…}, action, timestamp }
      realtime: { bot: {id,…}, data: { participant: {…}, action, timestamp } }
    """
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    raw_inner = data.get("data")
    inner: dict = raw_inner if isinstance(raw_inner, dict) else {}

    bot_session = _session_for_bot(session, bot_id)
    if not bot_session or not bot_session.meeting_id:
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}
    meeting_id = bot_session.meeting_id

    participant = inner.get("participant") or data.get("participant") or {}
    participant_id = participant.get("id") or participant.get("participant_id")
    if not participant_id:
        # Non-per-participant events (``participant_events.done`` /
        # ``.processing`` fire at resource-lifecycle granularity with no
        # participant in the payload) — ack and ignore.
        return {"received": True, "handled": False, "reason": "no_participant_id"}

    action = event.split(".")[-1]  # 'join' | 'leave' | 'update' | ...
    if action not in ("join", "leave", "update"):
        return {"received": True, "handled": False, "reason": f"skip_{action}"}

    # Recall's timestamps come as either ISO strings or a
    # {"relative": <float>, "absolute": <ISO>} object. Postgres only
    # accepts the ISO string, so pull `.absolute` out when it's a dict.
    raw_ts = (
        inner.get("timestamp")
        or inner.get("updated_at")
        or data.get("timestamp")
        or data.get("updated_at")
    )
    timestamp = raw_ts.get("absolute") if isinstance(raw_ts, dict) else raw_ts

    row: dict = {
        "meeting_id": meeting_id,
        "recall_participant_id": str(participant_id),
        "speaker_label": participant.get("name") or f"Participant {participant_id}",
        "speaker_name": participant.get("name"),
        "email_address": participant.get("email"),
    }
    if action == "join" and timestamp:
        row["joined_at"] = timestamp
    elif action == "leave" and timestamp:
        row["left_at"] = timestamp

    # meeting_participants has a partial unique index on
    # (meeting_id, recall_participant_id) — select → update-or-insert to
    # keep repeated deliveries idempotent.
    async with _WRITE_SEMAPHORE:
        existing = session.scalar(
            select(MeetingParticipant)
            .where(MeetingParticipant.meeting_id == meeting_id)
            .where(MeetingParticipant.recall_participant_id == str(participant_id))
            .limit(1)
        )
        if existing is not None:
            for key, value in row.items():
                setattr(existing, key, value)
        else:
            session.add(MeetingParticipant(**row))
        session.flush()

    with contextlib.suppress(Exception):
        await publish_meeting_event(meeting_id, "participant", row)
    return {"received": True, "handled": True, "action": action}


async def _handle_chat(
    _event: str, data: dict, session: Session
) -> dict:
    """Insert in-meeting chat messages captured by Recall.

    Accepts both shapes:
      legacy:   { bot_id, message: {…} }
      realtime: { bot: {id,…}, data: { message|chat_message: {…} } }
    """
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    raw_inner = data.get("data")
    inner: dict = raw_inner if isinstance(raw_inner, dict) else {}

    bot_session = _session_for_bot(session, bot_id)
    if not bot_session or not bot_session.meeting_id:
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}
    meeting_id = bot_session.meeting_id

    message = (
        inner.get("message")
        or inner.get("chat_message")
        or data.get("message")
        or data.get("chat_message")
        or {}
    )
    message_id = message.get("id") or message.get("message_id")
    text = message.get("text") or message.get("content") or ""
    if not text:
        return {"received": True, "handled": False, "reason": "empty_message"}

    sender = message.get("sender") or message.get("participant") or {}
    row = {
        "meeting_id": meeting_id,
        "org_id": bot_session.org_id,
        "sender_name": sender.get("name"),
        "sender_email": sender.get("email"),
        "text": text,
        "sent_at": (
            message.get("timestamp")
            or message.get("sent_at")
            or data.get("timestamp")
        ),
        "recall_message_id": str(message_id) if message_id else None,
    }
    if row["sent_at"] is None:
        # Can't insert without a sent_at (NOT NULL). Skip.
        return {"received": True, "handled": False, "reason": "no_timestamp"}

    # meeting_chat_messages has a unique index on recall_message_id — when
    # present, select → update-or-insert so a replay collapses in place;
    # otherwise straight insert.
    async with _WRITE_SEMAPHORE:
        existing = None
        if row["recall_message_id"]:
            existing = session.scalar(
                select(MeetingChatMessage).where(
                    MeetingChatMessage.recall_message_id == row["recall_message_id"]
                )
            )
        if existing is not None:
            for key, value in row.items():
                setattr(existing, key, value)
        else:
            session.add(MeetingChatMessage(**row))
        session.flush()

    with contextlib.suppress(Exception):
        await publish_meeting_event(meeting_id, "chat", row)
    return {"received": True, "handled": True}
