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
    if event in ("transcript.partial", "transcript.final"):
        return await _handle_transcript(event, data, service_supabase)

    # --- Lifecycle events ----------------------------------------------------
    if event in ("bot.status_change", "bot.call_ended", "bot.done"):
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
    return {"received": True, "handled": False, "event": event}


async def _handle_transcript(
    event: str, data: dict, service_supabase: Client
) -> dict:
    bot_id = data.get("bot_id") or ""
    segment = data.get("segment") or {}

    session = _session_for_bot(service_supabase, bot_id)
    if not session:
        logger.warning("recall_webhook_unknown_bot bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "unknown_bot"}
    meeting_id = session.get("meeting_id")
    if not meeting_id:
        logger.warning("recall_webhook_no_meeting bot_id=%s", bot_id)
        return {"received": True, "handled": False, "reason": "no_meeting"}

    recall_segment_id = segment.get("id")
    if not recall_segment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment missing id",
        )

    is_partial = event == "transcript.partial"
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
    (``call_ended`` / ``done``), we flip the bot session + meeting rows and
    fire ``meeting/uploaded`` so the post-meeting Inngest pipeline runs.
    """
    bot_id = data.get("bot_id") or ""
    recall_status = (data.get("status") or {}).get("code") or ""

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
        # Flip the meeting status and enqueue the post-meeting pipeline so
        # embeddings + analyses run over the finalized transcript.
        service_supabase.table("meetings").update({"status": "uploaded"}).eq(
            "id", session["meeting_id"]
        ).execute()
        await send_event(
            "meeting/uploaded",
            {
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

    Payload shape (Recall docs may vary by API version):
      { bot_id, participant: { id, name, email?, is_host? }, action, timestamp }
    """
    bot_id = data.get("bot_id") or ""
    session = _session_for_bot(service_supabase, bot_id)
    if not session or not session.get("meeting_id"):
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}

    participant = data.get("participant") or {}
    participant_id = participant.get("id") or participant.get("participant_id")
    if not participant_id:
        return {"received": True, "handled": False, "reason": "no_participant_id"}

    action = event.split(".")[-1]  # 'join' | 'leave' | 'update' | ...
    timestamp = data.get("timestamp") or data.get("updated_at")

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

    Payload shape (typical):
      { bot_id, message: { id, sender: { name, email? }, text, timestamp } }
    """
    bot_id = data.get("bot_id") or ""
    session = _session_for_bot(service_supabase, bot_id)
    if not session or not session.get("meeting_id"):
        return {"received": True, "handled": False, "reason": "unknown_bot_or_meeting"}

    message = data.get("message") or data.get("chat_message") or {}
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
