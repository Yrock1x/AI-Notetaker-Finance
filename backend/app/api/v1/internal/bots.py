"""/internal/* — Recall.ai bot lifecycle: start, stop, auto-schedule, finalize."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.internal._common import (
    require_internal_token,
)
from app.core.config import settings
from app.db.deps import get_db
from app.db.models import (
    Meeting,
    MeetingBotSession,
    MeetingParticipant,
    Transcript,
    TranscriptSegment,
)
from app.integrations.recall.client import RecallClient

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# /internal/bot/start  and  /internal/bot/stop
# ---------------------------------------------------------------------------
class BotRequest(BaseModel):
    session_id: str


class BotResponse(BaseModel):
    session_id: str
    status: str
    recall_bot_id: str | None = None


@router.post(
    "/bot/start",
    response_model=BotResponse,
    dependencies=[Depends(require_internal_token)],
)
async def bot_start(
    body: BotRequest,
    session: Session = Depends(get_db),
) -> BotResponse:
    # Fail fast before touching the DB — if the Recall key is missing, the
    # call can never succeed and Inngest would otherwise keep retrying while
    # leaving the meeting row in a half-populated 'recording' state.
    if not settings.recall_api_key:
        raise HTTPException(status_code=500, detail="RECALL_API_KEY not configured")

    bot_session = session.get(MeetingBotSession, body.session_id)
    if bot_session is None:
        raise HTTPException(status_code=404, detail="Bot session not found")

    # Ensure a meetings row exists — without one, live-transcript writes have
    # nowhere to land and the Live panel can't subscribe. Leave status as
    # 'scheduled'; the Recall status webhook flips it to 'recording' only
    # once the bot is actually in-call.
    meeting_id = bot_session.meeting_id
    if not meeting_id:
        platform_source_map = {
            "zoom": "zoom",
            "teams": "teams",
            "google_meet": "meet",
        }
        platform_label_map = {
            "zoom": "Zoom call",
            "teams": "Teams meeting",
            "google_meet": "Google Meet",
        }
        # Fallback title used when bot_start has to create the meeting row
        # itself (e.g. bot session was scheduled without a preceding meeting).
        # Matches the format produced by useScheduleBot so /bot/finalize can
        # recognise + replace it once Recall reports the real title.
        now = datetime.now(UTC)
        date_label = now.strftime("%b %-d, %-I:%M %p")
        fallback_title = (
            f"{platform_label_map.get(bot_session.platform, 'Live meeting')}"
            f" — {date_label}"
        )
        new_meeting = Meeting(
            org_id=bot_session.org_id,
            deal_id=bot_session.deal_id,
            title=fallback_title,
            source=platform_source_map.get(bot_session.platform, "upload"),
            source_url=bot_session.meeting_url,
            status="scheduled",
            created_by=bot_session.created_by,
        )
        session.add(new_meeting)
        session.flush()
        meeting_id = new_meeting.id
        bot_session.meeting_id = meeting_id
        session.flush()

    recall = RecallClient(api_key=settings.recall_api_key, region=settings.recall_region)

    # Per-bot realtime webhook. Recall v1 only accepts transcript +
    # participant_events.* here — bot.* lifecycle events (status_change,
    # done, fatal) come through Recall's account-level webhook configured
    # in the dashboard. Both land on the same /api/v1/webhooks/recall
    # handler, which also accepts the dashboard-signed payloads via
    # RECALL_WEBHOOK_SECRET.
    webhook_url = f"{settings.public_api_url.rstrip('/')}/api/v1/webhooks/recall"
    realtime_events = [
        "transcript.data",
        "transcript.partial_data",
        "participant_events.join",
        "participant_events.leave",
        "participant_events.update",
        "participant_events.chat_message",
    ]

    try:
        bot_data = await recall.create_bot(
            meeting_url=bot_session.meeting_url,
            bot_name="CogniSuite Notetaker",
            recording_config={
                "transcript": {"provider": {"deepgram_streaming": {}}},
                # Stream participant join/leave events and in-meeting chat via
                # the meeting platform's own channels. Recall fans these out to
                # the same webhook as transcript events.
                "participant_events": {
                    "provider": {"meeting_platform": {}},
                },
                "chat": {
                    "provider": {"meeting_platform": {}},
                },
                "realtime_endpoints": [
                    {
                        "type": "webhook",
                        "url": webhook_url,
                        "events": realtime_events,
                    }
                ],
            },
            metadata={
                "session_id": bot_session.id,
                "org_id": bot_session.org_id,
                "deal_id": bot_session.deal_id,
                "meeting_id": meeting_id,
            },
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        logger.error(
            "recall_create_bot_failed session_id=%s status=%s body=%s",
            bot_session.id,
            exc.response.status_code,
            detail,
        )
        bot_session.status = "failed"
        # Persist the failed state now — get_db rolls back on the raise below,
        # which would otherwise discard it and leave a half-populated session.
        session.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Recall.ai rejected bot create ({exc.response.status_code}): {detail}",
        ) from exc
    except Exception as exc:
        logger.exception("recall_create_bot_error session_id=%s", bot_session.id)
        bot_session.status = "failed"
        session.commit()
        raise HTTPException(status_code=502, detail=f"Recall.ai call failed: {exc}") from exc

    recall_bot_id = bot_data.get("id")
    bot_session.status = "joining"
    bot_session.recall_bot_id = recall_bot_id
    bot_session.live_transcript_channel = f"transcripts:{meeting_id}"
    session.flush()

    return BotResponse(
        session_id=bot_session.id, status="joining", recall_bot_id=recall_bot_id
    )


@router.post(
    "/bot/stop",
    response_model=BotResponse,
    dependencies=[Depends(require_internal_token)],
)
async def bot_stop(
    body: BotRequest,
    session: Session = Depends(get_db),
) -> BotResponse:
    bot_session = session.get(MeetingBotSession, body.session_id)
    if bot_session is None:
        raise HTTPException(status_code=404, detail="Bot session not found")

    if settings.recall_api_key and bot_session.recall_bot_id:
        try:
            recall = RecallClient(api_key=settings.recall_api_key, region=settings.recall_region)
            await recall.leave_bot(bot_session.recall_bot_id)
        except Exception:
            logger.exception("recall_leave_failed bot_id=%s", bot_session.recall_bot_id)

    new_status = (
        "cancelled"
        if bot_session.status in ("scheduled", "joining")
        else "completed"
    )
    bot_session.status = new_status
    session.flush()

    return BotResponse(
        session_id=bot_session.id,
        status=new_status,
        recall_bot_id=bot_session.recall_bot_id,
    )


# ---------------------------------------------------------------------------
# /internal/bot/auto-schedule-due — find calendar-synced meetings that are
# about to start and pre-create a meeting_bot_sessions row for each. The
# Inngest cron that calls this fans out a bot/scheduled event per returned
# session id so the existing start-bot handler does the actual Recall call.
# ---------------------------------------------------------------------------
class AutoScheduleDueResponse(BaseModel):
    scheduled: list[dict]  # each: {session_id, meeting_id, deal_id}


# Platforms accepted by meeting_bot_sessions.platform — map the wider set
# of meetings.source values down to the three Recall supports.
_SOURCE_TO_PLATFORM: dict[str, str] = {
    "zoom": "zoom",
    "teams": "teams",
    "meet": "google_meet",
    "google_meet": "google_meet",
}


@router.post(
    "/bot/auto-schedule-due",
    response_model=AutoScheduleDueResponse,
    dependencies=[Depends(require_internal_token)],
)
async def bot_auto_schedule_due(
    session: Session = Depends(get_db),
) -> AutoScheduleDueResponse:
    now = datetime.now(UTC)
    # Grace window at the front edge: cover meetings that started up to
    # 15 min ago so a late dealassignment (or a cron tick that just
    # missed the start) still spawns a bot into the call. Back edge
    # stays 10 min ahead so we join a bit before the meeting begins.
    window_start = now - timedelta(minutes=15)
    window_end = now + timedelta(minutes=10)

    candidates = session.scalars(
        select(Meeting)
        .where(Meeting.bot_enabled.is_(True))
        .where(Meeting.status == "uploading")
        .where(Meeting.deal_id.is_not(None))
        .where(Meeting.source_url.is_not(None))
        .where(Meeting.meeting_date >= window_start.isoformat())
        .where(Meeting.meeting_date <= window_end.isoformat())
    ).all()

    scheduled: list[dict] = []
    for m in candidates:
        platform = _SOURCE_TO_PLATFORM.get((m.source or "").lower())
        if not platform:
            # Upload-only / unrecognised source — nothing to do.
            continue

        # Dedupe: skip if any live session already exists for this meeting.
        # Active statuses are the ones a cron rerun shouldn't clobber.
        existing = session.scalar(
            select(MeetingBotSession.id)
            .where(MeetingBotSession.meeting_id == m.id)
            .where(
                MeetingBotSession.status.in_(
                    ["scheduled", "joining", "recording", "completed"]
                )
            )
            .limit(1)
        )
        if existing:
            continue

        session_row = MeetingBotSession(
            org_id=m.org_id,
            deal_id=m.deal_id,
            meeting_id=m.id,
            platform=platform,
            meeting_url=m.source_url,
            status="scheduled",
            scheduled_start=m.meeting_date,
            created_by=m.created_by,
        )
        session.add(session_row)
        session.flush()
        scheduled.append(
            {
                "session_id": session_row.id,
                "meeting_id": m.id,
                "deal_id": m.deal_id,
            }
        )

    logger.info("bot_auto_schedule_due scheduled=%d", len(scheduled))
    return AutoScheduleDueResponse(scheduled=scheduled)


# ---------------------------------------------------------------------------
# /internal/bot/finalize — post-meeting sync for bot-recorded meetings.
#
# Runs after Recall signals ``bot.done``. Pulls the authoritative transcript,
# participants, and meeting metadata from Recall's recording ``media_shortcuts``
# (S3-signed URLs that expire, so we pull + persist immediately). This is the
# bot equivalent of ``/internal/transcribe`` for uploaded audio — skipping
# Deepgram entirely because Recall already ran it during the call.
# ---------------------------------------------------------------------------
class FinalizeBotRequest(BaseModel):
    session_id: str


class FinalizeBotResponse(BaseModel):
    meeting_id: str
    transcript_id: str | None
    segment_count: int
    participant_count: int


@router.post(
    "/bot/finalize",
    response_model=FinalizeBotResponse,
    dependencies=[Depends(require_internal_token)],
)
async def bot_finalize(
    body: FinalizeBotRequest,
    session: Session = Depends(get_db),
) -> FinalizeBotResponse:
    bot_session = session.get(MeetingBotSession, body.session_id)
    if bot_session is None:
        raise HTTPException(status_code=404, detail="Bot session not found")
    if not bot_session.recall_bot_id:
        raise HTTPException(status_code=400, detail="Session has no recall_bot_id")
    if not bot_session.meeting_id:
        raise HTTPException(status_code=400, detail="Session has no meeting_id")
    meeting_id = bot_session.meeting_id

    if not settings.recall_api_key:
        raise HTTPException(status_code=500, detail="RECALL_API_KEY not configured")

    recall = RecallClient(
        api_key=settings.recall_api_key, region=settings.recall_region
    )
    bot = await recall.get_bot(bot_session.recall_bot_id)
    recordings = bot.get("recordings") or []
    if not recordings:
        logger.warning("bot_finalize_no_recording session_id=%s", bot_session.id)
        return FinalizeBotResponse(
            meeting_id=meeting_id,
            transcript_id=None,
            segment_count=0,
            participant_count=0,
        )
    shortcuts = (recordings[0].get("media_shortcuts") or {})

    # --- Transcript ----------------------------------------------------------
    # The transcript shortcut points to a JSON array of
    # { participant, words: [{text,start_timestamp:{relative,absolute},...}] }
    # entries, one per continuous speaker turn.
    transcript_id: str | None = None
    segments_written = 0
    full_text_parts: list[str] = []
    tr_url = ((shortcuts.get("transcript") or {}).get("data") or {}).get("download_url")
    turns: list[dict] = []
    if tr_url:
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.get(tr_url)
            r.raise_for_status()
            turns = r.json() or []

    segment_rows: list[dict] = []
    for idx, turn in enumerate(turns):
        words = turn.get("words") or []
        if not words:
            continue
        participant = turn.get("participant") or {}
        text = " ".join((w.get("text") or "").strip() for w in words if w.get("text"))
        if not text:
            continue
        full_text_parts.append(text)
        start = (words[0].get("start_timestamp") or {}).get("relative") or 0.0
        end = (words[-1].get("end_timestamp") or {}).get("relative") or start
        speaker_name = participant.get("name")
        segment_rows.append(
            {
                "meeting_id": meeting_id,
                "speaker_label": speaker_name or f"Speaker {participant.get('id', idx)}",
                "speaker_name": speaker_name,
                "text": text,
                "start_time": float(start),
                "end_time": float(end),
                "confidence": None,
                "segment_index": idx,
                "is_partial": False,
            }
        )

    if segment_rows:
        transcript = session.scalar(
            select(Transcript).where(Transcript.meeting_id == meeting_id)
        )
        if transcript is None:
            transcript = Transcript(
                org_id=bot_session.org_id, meeting_id=meeting_id
            )
            session.add(transcript)
        transcript.full_text = " ".join(full_text_parts)
        transcript.language = "en"
        transcript.word_count = sum(len(p.split()) for p in full_text_parts)
        session.flush()
        transcript_id = transcript.id
        # Drop any finalized segments written by a prior run, then insert fresh.
        # Live partials (is_partial=true) are left alone for the diff; they get
        # replaced by the upsert below when recall_segment_id matches.
        old_finalized = session.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_id)
            .where(TranscriptSegment.is_partial.is_(False))
        ).all()
        for old in old_finalized:
            session.delete(old)
        session.flush()
        for row in segment_rows:
            session.add(
                TranscriptSegment(transcript_id=transcript_id, **row)
            )
        session.flush()
        segments_written = len(segment_rows)

    # --- Participants --------------------------------------------------------
    # The transcript payload already carries every speaker who produced words;
    # fall back on that instead of the (often empty) participant_events
    # shortcut so we at least record who actually spoke.
    participants_by_id: dict[str, dict] = {}
    for turn in turns:
        p = turn.get("participant") or {}
        pid = p.get("id")
        if pid is None:
            continue
        participants_by_id[str(pid)] = {
            "meeting_id": meeting_id,
            "recall_participant_id": str(pid),
            "speaker_label": p.get("name") or f"Participant {pid}",
            "speaker_name": p.get("name"),
            "email_address": p.get("email"),
        }
    participant_count = 0
    if participants_by_id:
        # meeting_participants has a *partial* unique index on
        # (meeting_id, recall_participant_id). Rebuild the recall-sourced rows
        # — safe because /bot/finalize is the authoritative post-call pull.
        old_participants = session.scalars(
            select(MeetingParticipant)
            .where(MeetingParticipant.meeting_id == meeting_id)
            .where(MeetingParticipant.recall_participant_id.is_not(None))
        ).all()
        for old_participant in old_participants:
            session.delete(old_participant)
        session.flush()
        for prow in participants_by_id.values():
            session.add(MeetingParticipant(**prow))
        session.flush()
        participant_count = len(participants_by_id)

    # --- Meeting metadata (title) -------------------------------------------
    meta_url = ((shortcuts.get("meeting_metadata") or {}).get("data") or {}).get(
        "download_url"
    )
    if meta_url:
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                rm = await http.get(meta_url)
                rm.raise_for_status()
                meta = rm.json() or {}
            real_title = (meta.get("title") or "").strip()
            if real_title:
                # Only overwrite auto-generated placeholders — never the user's
                # chosen title. Placeholders all start with a known prefix.
                current_meeting = session.get(Meeting, meeting_id)
                cur_title = (current_meeting.title if current_meeting else "") or ""
                if current_meeting is not None and cur_title.startswith(
                    (
                        "Bot meeting — ",
                        "Live meeting — ",
                        "Zoom call — ",
                        "Teams meeting — ",
                        "Google Meet — ",
                    )
                ):
                    current_meeting.title = real_title
                    session.flush()
        except Exception:
            logger.exception("bot_finalize_meta_failed session_id=%s", bot_session.id)

    # --- Flip meeting to 'uploaded' so downstream pipelines treat it as ready
    meeting_row = session.get(Meeting, meeting_id)
    if meeting_row is not None:
        meeting_row.status = "uploaded"
        session.flush()

    return FinalizeBotResponse(
        meeting_id=meeting_id,
        transcript_id=transcript_id,
        segment_count=segments_written,
        participant_count=participant_count,
    )


