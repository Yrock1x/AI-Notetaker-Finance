"""Recall.ai webhook — single endpoint that handles both real-time
transcript events and bot lifecycle events.

Transcript events (``transcript.partial`` / ``transcript.final``) upsert
into ``transcript_segments`` keyed on ``recall_segment_id`` so partials get
replaced in place by their finalized text. Supabase Realtime broadcasts
each change to the Live panel.

Lifecycle events (``bot.status_change``) flip ``meeting_bot_sessions.status``
and, when the call ends, fire ``meeting/uploaded`` into Inngest so the
post-meeting pipeline (embed + analyze) kicks off automatically.

Configure one webhook URL in the Recall.ai dashboard that points here —
every event type lands on this handler.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from supabase import Client

from app.core.config import settings
from app.dependencies import get_service_supabase
from app.integrations.inngest import send_event

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------
def _verify_recall_signature(raw_body: bytes, header_sig: str | None) -> None:
    if not settings.recall_webhook_secret:
        # In dev we accept unsigned webhooks to simplify local testing.
        return
    if not header_sig:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Recall signature header",
        )
    expected = hmac.new(
        settings.recall_webhook_secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, header_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Recall signature",
        )


# ---------------------------------------------------------------------------
# Shared: look up the bot session row for a bot_id
# ---------------------------------------------------------------------------
def _session_for_bot(service_supabase: Client, bot_id: str) -> dict | None:
    rows = (
        service_supabase.table("meeting_bot_sessions")
        .select("id, meeting_id, deal_id, org_id, status")
        .eq("recall_bot_id", bot_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Endpoint: unified handler
# ---------------------------------------------------------------------------
@router.post("")
@router.post("/transcript")  # kept for back-compat if old URLs are still in Recall
async def recall_webhook(
    request: Request,
    x_recall_signature: str | None = Header(default=None),
    service_supabase: Client = Depends(get_service_supabase),
) -> dict:
    raw_body = await request.body()
    _verify_recall_signature(raw_body, x_recall_signature)

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        ) from exc

    event = payload.get("event", "")
    data = payload.get("data", {}) or {}

    # --- Transcript events ---------------------------------------------------
    # Recall's realtime_endpoints spell these "transcript.partial_data" /
    # "transcript.data"; the older per-bot push used "transcript.partial" /
    # "transcript.final". Handle both so we stay resilient across API versions.
    if event.startswith("transcript."):
        return await _handle_transcript(event, data, service_supabase)

    # --- Lifecycle events ----------------------------------------------------
    if event in ("bot.status_change", "bot.call_ended", "bot.done", "bot.fatal"):
        return await _handle_status_change(event, data, service_supabase)

    # --- Participant join / leave -------------------------------------------
    if event.startswith("participant_events.") or event.startswith(
        "participant."
    ):
        return await _handle_participant(event, data, service_supabase)

    # --- In-meeting chat -----------------------------------------------------
    if event.startswith("chat_messages.") or event.startswith("chat."):
        return await _handle_chat(event, data, service_supabase)

    # Anything else — ack and ignore. Recall fires many event types.
    logger.info("recall_webhook_unhandled event=%s", event)
    return {"received": True, "handled": False, "event": event}


async def _handle_transcript(
    event: str, data: dict, service_supabase: Client
) -> dict:
    # Recall sends transcript events in two very different shapes:
    #  1. Legacy per-bot push: {"event":"transcript.partial", "data":
    #     {"bot_id":"…", "segment":{"id","speaker","text","start_time",…}}}
    #  2. realtime_endpoints push: {"event":"transcript.partial_data", "data":
    #     {"bot":{"id","metadata"}, "data":{"participant":{…},"words":[…]}}}
    # Normalise both into the same row before upsert so the DB stays uniform.
    is_partial = event.endswith(".partial") or event.endswith(".partial_data")

    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    # Realtime payloads nest the body under data.data
    inner = data.get("data") if isinstance(data.get("data"), dict) else None
    segment = data.get("segment") or {}

    session = _session_for_bot(service_supabase, bot_id)
    if not session:
        logger.warning("recall_webhook_unknown_bot bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "unknown_bot"}
    meeting_id = session.get("meeting_id")
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

    (
        service_supabase.table("transcript_segments")
        .upsert(row, on_conflict="recall_segment_id")
        .execute()
    )
    return {"received": True, "handled": True, "is_partial": is_partial}


async def _handle_status_change(
    event: str, data: dict, service_supabase: Client
) -> dict:
    """Bot lifecycle handoff.

    Maps Recall's ``code`` field (from ``data.status``) to our
    ``meeting_bot_sessions.status`` values. When the call truly ends
    (``call_ended`` / ``done``), we fire ``meeting/bot-completed`` so the
    bot-specific Inngest pipeline (pull transcript + participants from
    Recall, then embed + analyze) runs.
    """
    # Realtime-endpoints payloads: {"bot":{"id","metadata"}, "data":{"code",…}}
    # Legacy payloads:             {"bot_id":"…", "status":{"code":"…"}}
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    inner = data.get("data") if isinstance(data.get("data"), dict) else None
    recall_status = (
        (inner or {}).get("code")
        or (data.get("status") or {}).get("code")
        or ""
    )

    session = _session_for_bot(service_supabase, bot_id)
    if not session:
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

    update = {"status": next_status}
    if next_status == "recording":
        update["actual_start"] = data.get("updated_at") or "now()"
    elif next_status in ("completed", "failed"):
        update["actual_end"] = data.get("updated_at") or "now()"

    # Supabase-py rejects "now()" as a value — use None and let the trigger
    # default to the current timestamp via ``updated_at`` instead; fall back
    # to client-side ISO when we have a real timestamp from Recall.
    update.pop("actual_start", None) if update.get("actual_start") == "now()" else None
    update.pop("actual_end", None) if update.get("actual_end") == "now()" else None

    service_supabase.table("meeting_bot_sessions").update(update).eq(
        "id", session["id"]
    ).execute()

    # Keep meetings.status in sync with the bot's real lifecycle. bot_start
    # intentionally leaves the meeting at 'scheduled' until Recall confirms
    # the bot is in-call, so the Live tab's "waiting" state is truthful.
    if next_status == "recording" and session.get("meeting_id"):
        service_supabase.table("meetings").update({"status": "recording"}).eq(
            "id", session["meeting_id"]
        ).execute()
    elif next_status == "completed" and session.get("meeting_id"):
        # Bot meetings take a dedicated pipeline that pulls the authoritative
        # transcript + participants from Recall's recording shortcuts —
        # Deepgram already ran during the call, so the file-upload path
        # (``meeting/uploaded``) doesn't apply. The finalize step flips
        # meetings.status to 'uploaded' itself once the pull succeeds.
        await send_event(
            "meeting/bot-completed",
            {
                "session_id": session["id"],
                "meeting_id": session["meeting_id"],
                "deal_id": session.get("deal_id", ""),
            },
        )

    return {
        "received": True,
        "handled": True,
        "next_status": next_status,
        "recall_status": recall_status,
    }


async def _handle_participant(
    event: str, data: dict, service_supabase: Client
) -> dict:
    """Upsert ``meeting_participants`` from Recall participant_events.*.

    Accepts both the legacy shape and the realtime_endpoints shape:
      legacy:   { bot_id, participant: {…}, action, timestamp }
      realtime: { bot: {id,…}, data: { participant: {…}, action, timestamp } }
    """
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}

    session = _session_for_bot(service_supabase, bot_id)
    if not session or not session.get("meeting_id"):
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}

    participant = inner.get("participant") or data.get("participant") or {}
    participant_id = participant.get("id") or participant.get("participant_id")
    if not participant_id:
        return {"received": True, "handled": False, "reason": "no_participant_id"}

    action = event.split(".")[-1]  # 'join' | 'leave' | 'update' | ...
    timestamp = (
        inner.get("timestamp")
        or inner.get("updated_at")
        or data.get("timestamp")
        or data.get("updated_at")
    )

    row: dict = {
        "meeting_id": session["meeting_id"],
        "recall_participant_id": str(participant_id),
        "speaker_label": participant.get("name") or f"Participant {participant_id}",
        "speaker_name": participant.get("name"),
        "email_address": participant.get("email"),
    }
    if action == "join":
        row["joined_at"] = timestamp
    elif action == "leave":
        row["left_at"] = timestamp

    (
        service_supabase.table("meeting_participants")
        .upsert(row, on_conflict="meeting_id,recall_participant_id")
        .execute()
    )
    return {"received": True, "handled": True, "action": action}


async def _handle_chat(
    _event: str, data: dict, service_supabase: Client
) -> dict:
    """Insert in-meeting chat messages captured by Recall.

    Accepts both shapes:
      legacy:   { bot_id, message: {…} }
      realtime: { bot: {id,…}, data: { message|chat_message: {…} } }
    """
    bot = data.get("bot") or {}
    bot_id = bot.get("id") or data.get("bot_id") or ""
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}

    session = _session_for_bot(service_supabase, bot_id)
    if not session or not session.get("meeting_id"):
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}

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
        "meeting_id": session["meeting_id"],
        "org_id": session["org_id"],
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

    if row["recall_message_id"]:
        (
            service_supabase.table("meeting_chat_messages")
            .upsert(row, on_conflict="recall_message_id")
            .execute()
        )
    else:
        service_supabase.table("meeting_chat_messages").insert(row).execute()
    return {"received": True, "handled": True}
