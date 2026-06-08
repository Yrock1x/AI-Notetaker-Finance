"""Internal service-to-service endpoints invoked by Inngest functions.

These endpoints carry out the heavy Python-side work (Deepgram, Fireworks,
Recall.ai, file extraction) that Inngest's JavaScript orchestration calls
into. Every request must carry the shared ``X-Internal-Token`` header so
nobody on the public internet can trigger a pipeline step directly.

None of these endpoints are called from the browser — they live under
``/api/v1/internal/*`` and the frontend has no knowledge of them.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.db.models import (
    Document,
    Embedding,
    GraphSubscription,
    IntegrationCredential,
    Meeting,
    MeetingBotSession,
    MeetingParticipant,
    Transcript,
    TranscriptSegment,
)
from app.db.vectors import delete_vectors, upsert_vector
from app.dependencies import get_llm_router
from app.integrations.deepgram.client import DeepgramClient
from app.integrations.deepgram.processor import DiarizationProcessor
from app.integrations.recall.client import RecallClient
from app.llm.chunking import DocumentChunker, TranscriptChunker
from app.services.analysis_service import AnalysisService
from app.storage import local as storage
from app.utils.file_processing import (
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_xlsx,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Service-to-service auth
# ---------------------------------------------------------------------------
def require_internal_token(
    x_internal_token: str | None = Header(default=None),
) -> None:
    expected = settings.worker_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WORKER_INTERNAL_TOKEN is not configured",
        )
    if x_internal_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token",
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
MEETINGS_BUCKET = "meeting-recordings"
DOCUMENTS_BUCKET = "deal-documents"

# Map a meeting recording's file extension to a Deepgram-friendly mimetype.
_EXT_MIMETYPES: dict[str, str] = {
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "aac": "audio/aac",
}


def _mimetype_for_key(file_key: str) -> str:
    """Pick an audio mimetype from a storage key's extension (default mp4)."""
    ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
    return _EXT_MIMETYPES.get(ext, "audio/mp4")


def _dedupe_zoom_google_rows(
    session: Session,
    org_id: Any,
    dates: list[str],
) -> None:
    """Collapse Google+Zoom duplicates into one Zoom-sourced row.

    When a user schedules a Zoom meeting that auto-creates a Google Calendar
    event, both providers sync the same underlying call. The Zoom row has
    the real ``us05web.zoom.us/j/<id>`` URL; the Google row only has an
    ``htmlLink`` fallback (or a ``source='zoom'`` row we built from the
    description). After each sync we look at the dates we just touched and
    merge any same-time pair into the Zoom row so:
      - The Calendar view + Dashboard widget show one card, not two.
      - Any user-set ``deal_id`` / ``bot_enabled`` on either row is
        preserved on the surviving Zoom row.
    """
    from app.integrations.zoom.urls import extract_zoom_meeting_id

    if not dates:
        return
    rows = (
        session.scalars(
            select(Meeting)
            .where(Meeting.org_id == str(org_id))
            .where(Meeting.meeting_date.in_(list(set(dates))))
        ).all()
    )

    # Group by meeting_date — a Zoom meeting + its Google shadow share the
    # same start time down to the second, so that's a stable join key.
    by_date: dict[str, list[Meeting]] = {}
    for r in rows:
        by_date.setdefault(r.meeting_date, []).append(r)

    for date_rows in by_date.values():
        if len(date_rows) < 2:
            continue
        # Prefer the row that came directly from Zoom's own calendar API
        # as the canonical one — its source_url is always the real
        # ``us05web.zoom.us/j/…`` join link with no HTML cruft. Google-
        # sourced rows can also carry source='zoom' (we parse the Zoom
        # URL out of the event description), but that URL may have been
        # pasted from a template and is less reliable.
        zoom_row = next(
            (
                r
                for r in date_rows
                if r.source == "zoom" and r.external_provider == "zoom"
            ),
            None,
        )
        if not zoom_row:
            zoom_row = next(
                (r for r in date_rows if r.source == "zoom"),
                None,
            )
        if not zoom_row:
            continue
        zoom_id = extract_zoom_meeting_id(zoom_row.source_url or "")

        for other in date_rows:
            if other.id == zoom_row.id:
                continue
            # Two rows for the SAME provider at the same second — don't
            # merge; that would be destroying two real back-to-back
            # meetings (vanishingly rare but possible).
            if other.external_provider == zoom_row.external_provider:
                continue
            # Confirm the other row points at the same Zoom meeting
            # before deleting. If we can extract a meeting id from its
            # source_url and it doesn't match, leave both alone — they
            # really are different calls.
            other_zoom_id = extract_zoom_meeting_id(other.source_url or "")
            if zoom_id and other_zoom_id and other_zoom_id != zoom_id:
                continue
            # Merge user-set fields onto the surviving Zoom row.
            if not zoom_row.deal_id and other.deal_id:
                zoom_row.deal_id = other.deal_id
            # bot_enabled: prefer an explicit off (user opt-out) over on.
            if other.bot_enabled is False:
                zoom_row.bot_enabled = False
            session.delete(other)
    session.flush()


# ---------------------------------------------------------------------------
# /internal/transcribe
# ---------------------------------------------------------------------------
class TranscribeRequest(BaseModel):
    meeting_id: str


class TranscribeResponse(BaseModel):
    transcript_id: str
    segment_count: int


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    dependencies=[Depends(require_internal_token)],
)
async def transcribe_meeting(
    body: TranscribeRequest,
    session: Session = Depends(get_db),
) -> TranscribeResponse:
    """Call Deepgram on the meeting's uploaded audio file, write transcript +
    segments, return counts."""
    meeting = session.get(Meeting, body.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    file_key = meeting.file_key
    if not file_key:
        raise HTTPException(status_code=400, detail="Meeting has no file_key")

    # Read the recording from local object storage and hand the bytes to
    # Deepgram directly (no signed URL — the file lives on the worker disk).
    try:
        audio_bytes = storage.read_bytes(MEETINGS_BUCKET, file_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Meeting recording not found in storage"
        ) from exc

    if not settings.deepgram_api_key:
        raise HTTPException(
            status_code=500, detail="DEEPGRAM_API_KEY is not configured"
        )
    dg = DeepgramClient(api_key=settings.deepgram_api_key)
    deepgram_response = await dg.transcribe_bytes(
        audio_bytes, mimetype=_mimetype_for_key(file_key)
    )

    processor = DiarizationProcessor()
    segments = processor.process_response(deepgram_response)

    # Build the Transcript summary.
    full_text_parts: list[str] = []
    word_count = 0
    conf_sum = 0.0
    conf_n = 0
    for seg in segments:
        full_text_parts.append(seg.get("text", ""))
        word_count += len(seg.get("text", "").split())
        if seg.get("confidence") is not None:
            conf_sum += float(seg["confidence"])
            conf_n += 1

    # Upsert the transcript row keyed on meeting_id.
    transcript = session.scalar(
        select(Transcript).where(Transcript.meeting_id == meeting.id)
    )
    if transcript is None:
        transcript = Transcript(org_id=meeting.org_id, meeting_id=meeting.id)
        session.add(transcript)
    transcript.full_text = " ".join(full_text_parts)
    transcript.language = "en"
    transcript.deepgram_response = deepgram_response
    transcript.word_count = word_count
    transcript.confidence_score = (conf_sum / conf_n) if conf_n else None
    session.flush()

    # Insert segment rows. Delete any prior finalized segments first so a
    # re-run doesn't duplicate; live-streamed partials are untouched and
    # will be replaced by matching recall_segment_id upserts when the bot
    # finishes.
    existing_finalized = session.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting.id)
        .where(TranscriptSegment.is_partial.is_(False))
    ).all()
    for old in existing_finalized:
        session.delete(old)
    session.flush()

    for i, seg in enumerate(segments):
        session.add(
            TranscriptSegment(
                transcript_id=transcript.id,
                meeting_id=meeting.id,
                speaker_label=seg.get("speaker_label") or "Speaker",
                speaker_name=seg.get("speaker_name"),
                text=seg.get("text", ""),
                start_time=float(seg.get("start_time") or 0),
                end_time=float(seg.get("end_time") or 0),
                confidence=seg.get("confidence"),
                segment_index=int(seg.get("segment_index") or i),
                is_partial=False,
            )
        )
    session.flush()

    return TranscribeResponse(
        transcript_id=transcript.id, segment_count=len(segments)
    )


# ---------------------------------------------------------------------------
# /internal/embed
# ---------------------------------------------------------------------------
class EmbedRequest(BaseModel):
    meeting_id: str


class EmbedResponse(BaseModel):
    count: int


@router.post(
    "/embed",
    response_model=EmbedResponse,
    dependencies=[Depends(require_internal_token)],
)
async def embed_meeting(
    body: EmbedRequest,
    session: Session = Depends(get_db),
) -> EmbedResponse:
    """Chunk the meeting's finalized transcript segments, embed with
    Fireworks, and upsert into the ``embeddings`` table."""
    meeting = session.get(Meeting, body.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.deal_id:
        raise HTTPException(status_code=400, detail="Meeting has no deal_id")

    seg_rows = session.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting.id)
        .where(TranscriptSegment.is_partial.is_(False))
        .order_by(TranscriptSegment.start_time)
    ).all()
    if not seg_rows:
        return EmbedResponse(count=0)

    segments = [
        {
            "id": s.id,
            "speaker_label": s.speaker_label,
            "speaker_name": s.speaker_name,
            "text": s.text,
            "start_time": s.start_time,
            "end_time": s.end_time,
        }
        for s in seg_rows
    ]

    chunker = TranscriptChunker()
    chunks = chunker.chunk_segments(segments)
    if not chunks:
        return EmbedResponse(count=0)

    llm = get_llm_router()
    vectors = await llm.embed_batch([c.text for c in chunks])

    # Clear prior embeddings for this meeting's segments (rows + vectors).
    segment_ids = [s["id"] for s in segments]
    prior = session.scalars(
        select(Embedding)
        .where(Embedding.source_type == "transcript_segment")
        .where(Embedding.source_id.in_(segment_ids))
    ).all()
    if prior:
        delete_vectors(session, [e.id for e in prior])
        for e in prior:
            session.delete(e)
        session.flush()

    count = 0
    for chunk, vec in zip(chunks, vectors, strict=False):
        emb = Embedding(
            org_id=meeting.org_id,
            deal_id=meeting.deal_id,
            source_type="transcript_segment",
            source_id=chunk.source_id or meeting.id,
            chunk_text=chunk.text,
            chunk_index=chunk.index,
            metadata_json=chunk.metadata,
        )
        session.add(emb)
        session.flush()
        upsert_vector(
            session, embedding_id=emb.id, deal_id=meeting.deal_id, vector=vec
        )
        count += 1

    return EmbedResponse(count=count)


# ---------------------------------------------------------------------------
# /internal/analyze
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    meeting_id: str
    call_type: str = "summarization"
    requested_by: str | None = None


class AnalyzeResponse(BaseModel):
    analysis_id: str
    status: str


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(require_internal_token)],
)
async def analyze_meeting(
    body: AnalyzeRequest,
    session: Session = Depends(get_db),
) -> AnalyzeResponse:
    meeting = session.get(Meeting, body.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    svc = AnalysisService(session=session, llm_router=get_llm_router())
    result = await svc.run_analysis(
        meeting_id=uuid.UUID(meeting.id),
        org_id=uuid.UUID(meeting.org_id),
        call_type=body.call_type,
        requested_by=uuid.UUID(body.requested_by) if body.requested_by else None,
    )
    return AnalyzeResponse(analysis_id=result["id"], status=result["status"])


# ---------------------------------------------------------------------------
# /internal/process-document
# ---------------------------------------------------------------------------
class ProcessDocumentRequest(BaseModel):
    document_id: str


class ProcessDocumentResponse(BaseModel):
    embedding_count: int


@router.post(
    "/process-document",
    response_model=ProcessDocumentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def process_document(
    body: ProcessDocumentRequest,
    session: Session = Depends(get_db),
) -> ProcessDocumentResponse:
    """Read a deal document from local storage, extract text, chunk, embed,
    and upsert into ``embeddings``."""
    doc = session.get(Document, body.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        file_bytes = storage.read_bytes(DOCUMENTS_BUCKET, doc.file_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Document not found in storage"
        ) from exc

    dtype = (doc.document_type or "").lower()
    if dtype == "pdf":
        extracted = await extract_text_from_pdf(file_bytes)
    elif dtype in ("docx", "doc"):
        extracted = await extract_text_from_docx(file_bytes)
    elif dtype in ("xlsx", "xls"):
        extracted = await extract_text_from_xlsx(file_bytes)
    else:
        try:
            extracted = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted = ""

    if not extracted.strip():
        doc.extracted_text = ""
        session.flush()
        return ProcessDocumentResponse(embedding_count=0)

    doc.extracted_text = extracted
    session.flush()

    chunker = DocumentChunker()
    chunks = chunker.chunk_text(extracted, source_id=doc.id)
    if not chunks:
        return ProcessDocumentResponse(embedding_count=0)

    llm = get_llm_router()
    vectors = await llm.embed_batch([c.text for c in chunks])

    # Wipe any prior embeddings for this document first (rows + vectors).
    prior = session.scalars(
        select(Embedding)
        .where(Embedding.source_type == "document_chunk")
        .where(Embedding.source_id == doc.id)
    ).all()
    if prior:
        delete_vectors(session, [e.id for e in prior])
        for e in prior:
            session.delete(e)
        session.flush()

    count = 0
    for c, v in zip(chunks, vectors, strict=False):
        emb = Embedding(
            org_id=doc.org_id,
            deal_id=doc.deal_id,
            source_type="document_chunk",
            source_id=doc.id,
            chunk_text=c.text,
            chunk_index=c.index,
            metadata_json=c.metadata,
        )
        session.add(emb)
        session.flush()
        upsert_vector(
            session, embedding_id=emb.id, deal_id=doc.deal_id, vector=v
        )
        count += 1

    return ProcessDocumentResponse(embedding_count=count)


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
        for old in old_participants:
            session.delete(old)
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
                if current_meeting is not None and (
                    cur_title.startswith("Bot meeting — ")
                    or cur_title.startswith("Live meeting — ")
                    or cur_title.startswith("Zoom call — ")
                    or cur_title.startswith("Teams meeting — ")
                    or cur_title.startswith("Google Meet — ")
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


# ---------------------------------------------------------------------------
# /internal/zoom/ingest
# ---------------------------------------------------------------------------
class ZoomIngestRequest(BaseModel):
    zoom_meeting_id: str
    download_url: str
    topic: str | None = None


class ZoomIngestResponse(BaseModel):
    meeting_id: str | None
    status: str


@router.post(
    "/zoom/ingest",
    response_model=ZoomIngestResponse,
    dependencies=[Depends(require_internal_token)],
)
async def zoom_ingest(
    body: ZoomIngestRequest,
    session: Session = Depends(get_db),
) -> ZoomIngestResponse:
    """Handle a ``recording.completed`` Zoom webhook.

    Flow:
      1. Try to attach the recording to an existing calendar-synced meeting
         (match on ``external_provider='zoom'`` + ``external_event_id``).
      2. If none, create an unassigned ``meetings`` row so the user can
         associate it with a deal from the calendar page.
      3. Download the recording into local object storage using any active
         Zoom OAuth credential in the org (best-effort).
      4. Fire ``meeting/uploaded`` so the post-meeting pipeline runs.
    """
    from app.services.oauth_tokens import decrypt_token

    zoom_meeting_id = str(body.zoom_meeting_id)

    # 1) Attribution: find an existing meetings row for this external event.
    match = session.scalar(
        select(Meeting)
        .where(Meeting.external_provider == "zoom")
        .where(Meeting.external_event_id == zoom_meeting_id)
        .limit(1)
    )

    if match is not None:
        meeting = match
        meeting_id = meeting.id
        org_id = meeting.org_id
        deal_id = meeting.deal_id or ""
    else:
        # Create an unassigned meeting. Pick any org with an active zoom
        # credential; if we can't find one, we have nothing to bind to.
        cred = session.scalar(
            select(IntegrationCredential)
            .where(IntegrationCredential.platform == "zoom")
            .where(IntegrationCredential.is_active.is_(True))
            .limit(1)
        )
        if cred is None:
            logger.warning(
                "zoom_ingest_no_credential zoom_meeting_id=%s", zoom_meeting_id
            )
            return ZoomIngestResponse(meeting_id=None, status="no_credential")
        org_id = cred.org_id
        created_by = cred.user_id
        new_meeting = Meeting(
            org_id=org_id,
            deal_id=None,
            title=body.topic or "Zoom recording",
            source="zoom",
            external_provider="zoom",
            external_event_id=zoom_meeting_id,
            status="uploading",
            created_by=created_by,
        )
        session.add(new_meeting)
        session.flush()
        meeting_id = new_meeting.id
        deal_id = ""

    # 2) Look up any active zoom credential (prefer one in the matched org).
    cred_for_org = session.scalar(
        select(IntegrationCredential)
        .where(IntegrationCredential.platform == "zoom")
        .where(IntegrationCredential.is_active.is_(True))
        .where(IntegrationCredential.org_id == org_id)
        .limit(1)
    )
    auth_header: dict[str, str] = {}
    if cred_for_org and cred_for_org.access_token_encrypted:
        try:
            zoom_access = decrypt_token(cred_for_org.access_token_encrypted)
            auth_header = {"Authorization": f"Bearer {zoom_access}"}
        except Exception:
            logger.exception("zoom_ingest_decrypt_failed")

    # 3) Download.
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.get(
                body.download_url,
                headers=auth_header,
                follow_redirects=True,
            )
            resp.raise_for_status()
            file_bytes = resp.content
    except Exception as exc:
        logger.exception("zoom_ingest_download_failed")
        raise HTTPException(
            status_code=502, detail=f"Zoom download failed: {exc}"
        ) from exc

    file_key = f"zoom/{meeting_id}.mp4"
    storage.save_bytes(MEETINGS_BUCKET, file_key, file_bytes)

    # 4) Flip status + fire the post-meeting pipeline.
    meeting_to_update = session.get(Meeting, meeting_id)
    if meeting_to_update is not None:
        meeting_to_update.file_key = file_key
        meeting_to_update.status = "uploaded"
        meeting_to_update.source_url = body.download_url
        session.flush()

    from app.integrations.inngest import send_event

    await send_event(
        "meeting/uploaded",
        {"meeting_id": meeting_id, "deal_id": deal_id},
    )

    logger.info(
        "zoom_ingest_done meeting_id=%s bytes=%d", meeting_id, len(file_bytes)
    )
    return ZoomIngestResponse(meeting_id=meeting_id, status="uploaded")


# ---------------------------------------------------------------------------
# /internal/teams/ingest-call-record
# ---------------------------------------------------------------------------
class TeamsIngestRequest(BaseModel):
    call_record_id: str
    tenant_id: str | None = None


class TeamsIngestResponse(BaseModel):
    call_record_id: str
    organizer: str | None
    participant_count: int
    handled: bool


@router.post(
    "/teams/ingest-call-record",
    response_model=TeamsIngestResponse,
    dependencies=[Depends(require_internal_token)],
)
async def teams_ingest_call_record(
    body: TeamsIngestRequest,
    session: Session = Depends(get_db),
) -> TeamsIngestResponse:
    """Fetch a Teams call record via Graph API and log its structure.

    This mirrors what the old Celery ``process_teams_webhook`` did: locate
    an active Teams credential, use its access token to fetch the expanded
    call record, and record participants/organizer. Full attribution to a
    deal/meeting is a product decision left to a later phase.
    """
    from uuid import UUID

    from app.services.oauth_tokens import get_valid_access_token

    # Accept both the new unified 'microsoft' platform and the legacy 'teams'.
    cred = session.scalar(
        select(IntegrationCredential)
        .where(IntegrationCredential.platform.in_(["microsoft", "teams"]))
        .where(IntegrationCredential.is_active.is_(True))
        .limit(1)
    )
    if cred is None:
        logger.warning(
            "teams_ingest_no_credential call_record_id=%s", body.call_record_id
        )
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    cred_org_id = cred.org_id
    cred_user_id = cred.user_id
    # Legacy rows may carry platform="teams"; the refresh dispatch only knows
    # "microsoft" (one OAuth app backs Teams/Outlook/Calendar).
    cred_platform = "microsoft" if cred.platform == "teams" else cred.platform
    try:
        access_token = await get_valid_access_token(
            session,
            org_id=UUID(cred_org_id),
            user_id=UUID(cred_user_id),
            platform=cred_platform,  # type: ignore[arg-type]
        )
    except Exception:
        logger.exception("teams_ingest_token_resolve_failed")
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    from app.integrations.teams.graph_client import GraphAPIClient

    graph = GraphAPIClient()
    try:
        record = await graph.get_call_record(access_token, body.call_record_id)
    except Exception:
        logger.exception(
            "teams_ingest_fetch_failed call_record_id=%s", body.call_record_id
        )
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    organizer = ((record.get("organizer") or {}).get("user") or {}).get("displayName")
    participants = record.get("participants", []) or []

    # Try to attach the call record to a calendar-synced meeting so analysis
    # lands on the same row the user already knows about. Teams' call record
    # doesn't carry the calendar event id directly; match on session start
    # time to the nearest upcoming event for the organizer (best-effort).
    sessions = record.get("sessions", []) or []
    start_times = [s.get("startDateTime") for s in sessions if s.get("startDateTime")]
    matched_meeting: Meeting | None = None
    if start_times:
        probe = start_times[0]
        # Find a 'microsoft' synced meeting in the same org within ±30 min of
        # the session start. ISO-8601 UTC timestamps sort lexically, so a
        # string window works as long as both sides are UTC ISO strings.
        try:
            probe_dt = datetime.fromisoformat(str(probe).replace("Z", "+00:00"))
            window_start = (probe_dt - timedelta(minutes=30)).isoformat()
            window_end = (probe_dt + timedelta(minutes=30)).isoformat()
        except ValueError:
            window_start = window_end = probe  # unparseable → exact-match fallback
        matched_meeting = session.scalar(
            select(Meeting)
            .where(Meeting.org_id == cred_org_id)
            .where(Meeting.external_provider == "microsoft")
            .where(Meeting.meeting_date >= window_start)
            .where(Meeting.meeting_date <= window_end)
            .order_by(Meeting.meeting_date)
            .limit(1)
        )

    if matched_meeting is None:
        new_meeting = Meeting(
            org_id=cred_org_id,
            deal_id=None,
            title=organizer and f"Teams call w/ {organizer}" or "Teams call",
            source="teams",
            external_provider="microsoft",
            external_event_id=body.call_record_id,
            status="uploaded",
            created_by=cred_user_id,
        )
        session.add(new_meeting)
        session.flush()
        meeting_id = new_meeting.id
    else:
        meeting_id = matched_meeting.id
        matched_meeting.status = "uploaded"
        session.flush()

    # Persist participants. Graph returns either the legacy `participants`
    # list or `participants_v2`; both shapes carry user.displayName and an
    # identifying id we reuse as the upsert key on
    # (meeting_id, recall_participant_id) so retries are idempotent.
    persisted = 0
    for p in participants:
        identity = (p.get("user") or {}) if isinstance(p, dict) else {}
        display_name = identity.get("displayName") or p.get("displayName") if isinstance(p, dict) else None
        upn = (
            identity.get("userPrincipalName")
            or (p.get("userPrincipalName") if isinstance(p, dict) else None)
        )
        external_id = (
            (p.get("id") if isinstance(p, dict) else None)
            or identity.get("id")
        )
        if not external_id and not display_name:
            continue
        try:
            existing_part = None
            if external_id is not None:
                existing_part = session.scalar(
                    select(MeetingParticipant)
                    .where(MeetingParticipant.meeting_id == meeting_id)
                    .where(
                        MeetingParticipant.recall_participant_id == str(external_id)
                    )
                    .limit(1)
                )
            speaker_label = display_name or upn or external_id or "Unknown"
            if existing_part is not None:
                existing_part.speaker_label = speaker_label
                existing_part.speaker_name = display_name
                existing_part.email_address = upn
            else:
                session.add(
                    MeetingParticipant(
                        meeting_id=meeting_id,
                        speaker_label=speaker_label,
                        speaker_name=display_name,
                        email_address=upn,
                        recall_participant_id=(
                            str(external_id) if external_id is not None else None
                        ),
                    )
                )
            session.flush()
            persisted += 1
        except Exception:
            logger.exception(
                "teams_ingest_participant_persist_failed meeting_id=%s",
                meeting_id,
            )

    logger.info(
        "teams_call_record_fetched call_record_id=%s organizer=%s participants=%d persisted=%d meeting_id=%s",
        body.call_record_id,
        organizer,
        len(participants),
        persisted,
        meeting_id,
    )
    return TeamsIngestResponse(
        call_record_id=body.call_record_id,
        organizer=organizer,
        participant_count=len(participants),
        handled=True,
    )


# ---------------------------------------------------------------------------
# /internal/calendar/sync — fan-in from Inngest cron
# ---------------------------------------------------------------------------
class CalendarSyncRequest(BaseModel):
    user_id: str
    org_id: str
    platform: str  # 'zoom' | 'microsoft' | 'google'
    lookahead_days: int = 14


class CalendarSyncResponse(BaseModel):
    platform: str
    events_seen: int
    meetings_upserted: int


@router.post(
    "/calendar/sync",
    response_model=CalendarSyncResponse,
    dependencies=[Depends(require_internal_token)],
)
async def calendar_sync(
    body: CalendarSyncRequest,
    session: Session = Depends(get_db),
) -> CalendarSyncResponse:
    """Pull upcoming events from the user's connected calendar and upsert
    them into ``meetings`` keyed on (org_id, external_provider, external_event_id).

    Synced rows land with ``deal_id = NULL`` until a user assigns one on
    the calendar page. The ``source`` column is populated based on the
    conferencing platform (zoom / teams / meet / outlook).
    """
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from app.services.oauth_tokens import get_valid_access_token

    if body.platform not in {"zoom", "microsoft", "google"}:
        raise HTTPException(400, f"Unsupported platform {body.platform}")

    org_uuid = UUID(body.org_id)
    user_uuid = UUID(body.user_id)
    now = datetime.now(UTC)
    time_max = now + timedelta(days=body.lookahead_days)

    access_token = await get_valid_access_token(
        session,
        org_id=org_uuid,
        user_id=user_uuid,
        platform=body.platform,  # type: ignore[arg-type]
    )

    events: list[dict] = []
    rows: list[dict] = []

    if body.platform == "zoom":
        from app.integrations.zoom.api_client import ZoomAPIClient

        client = ZoomAPIClient()
        events = await client.list_upcoming_meetings(access_token)
        for ev in events:
            start = ev.get("start_time")
            if not start:
                continue
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("topic") or "Zoom meeting",
                    "meeting_date": start,
                    "source": "zoom",
                    "source_url": ev.get("join_url"),
                    "external_event_id": str(ev.get("id")),
                    "external_provider": "zoom",
                    "status": "uploading",
                    "bot_enabled": True,
                    "created_by": str(user_uuid),
                }
            )

    elif body.platform == "microsoft":
        from app.integrations.teams.graph_client import GraphAPIClient

        graph = GraphAPIClient()
        events = await graph.get_calendar_events(
            access_token, user_id="me", time_min=now, time_max=time_max
        )
        for ev in events:
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue
            online = ev.get("onlineMeeting") or {}
            join_url = online.get("joinUrl")
            source = "teams" if join_url and "teams.microsoft.com" in join_url else "outlook"
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("subject") or "Meeting",
                    "meeting_date": start,
                    "source": source,
                    "source_url": join_url or ev.get("webLink"),
                    "external_event_id": ev.get("id"),
                    "external_provider": "microsoft",
                    "status": "uploading",
                    "bot_enabled": bool(join_url),
                    "created_by": str(user_uuid),
                }
            )

    elif body.platform == "google":
        from app.integrations.google.calendar_client import GoogleCalendarClient
        from app.integrations.zoom.urls import extract_zoom_url

        gcal = GoogleCalendarClient()
        events = await gcal.list_events(
            access_token, time_min=now, time_max=time_max
        )
        for ev in events:
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue  # all-day events don't have dateTime
            meet_url = GoogleCalendarClient.extract_meet_url(ev)
            # Zoom-via-Google case: event was created in Zoom (or pasted in
            # manually), Google stores the join URL in description/location.
            # Falling back here means the Google-sourced row can carry the
            # real Zoom URL + source='zoom' even before the Zoom OAuth sync
            # runs — the auto-schedule cron then has everything it needs.
            zoom_from_body = (
                None
                if meet_url
                else extract_zoom_url(ev.get("description"))
                or extract_zoom_url(ev.get("location"))
            )
            source, source_url = (
                ("meet", meet_url)
                if meet_url
                else ("zoom", zoom_from_body)
                if zoom_from_body
                else ("upload", ev.get("htmlLink"))
            )
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("summary") or "Meeting",
                    "meeting_date": start,
                    "source": source,
                    "source_url": source_url,
                    "external_event_id": ev.get("id"),
                    "external_provider": "google",
                    "status": "uploading",
                    "bot_enabled": bool(meet_url or zoom_from_body),
                    "created_by": str(user_uuid),
                }
            )

    upserted = 0
    # meetings has a PARTIAL unique index
    #   (org_id, external_provider, external_event_id) WHERE external_event_id
    # IS NOT NULL — select-then-insert-or-update per row to honour it.
    for row in rows:
        existing = session.scalar(
            select(Meeting)
            .where(Meeting.org_id == row["org_id"])
            .where(Meeting.external_provider == row["external_provider"])
            .where(Meeting.external_event_id == row["external_event_id"])
            .limit(1)
        )
        if existing is not None:
            # Preserve user-set state that the provider would otherwise
            # clobber on every re-sync:
            #   bot_enabled — user's on/off toggle
            #   deal_id     — user's assignment via AssignMeetingDialog
            # Everything else (title, meeting_date, source_url, status)
            # is safe to refresh from the provider.
            for k, v in row.items():
                if k in ("bot_enabled", "deal_id"):
                    continue
                setattr(existing, k, v)
        else:
            session.add(Meeting(**row))
        upserted += 1
    session.flush()

    # Dedupe pass. When a user has both Google Calendar sync and Zoom sync
    # active, the same Zoom meeting shows up as two rows: one from Zoom
    # (source='zoom', real join URL) and one from Google (source='meet' or
    # 'upload' with an htmlLink fallback). Keep the Zoom row — it has the
    # authoritative join URL — and collapse any duplicate into it.
    #
    # We only look at the dates we just touched to keep the query bounded.
    _dedupe_zoom_google_rows(session, org_uuid, [r["meeting_date"] for r in rows])

    logger.info(
        "calendar_sync_complete platform=%s user=%s events=%d upserted=%d",
        body.platform,
        body.user_id,
        len(events),
        upserted,
    )
    return CalendarSyncResponse(
        platform=body.platform,
        events_seen=len(events),
        meetings_upserted=upserted,
    )


# ---------------------------------------------------------------------------
# /internal/calendar/list-active-integrations — used by the Inngest fan-out
# ---------------------------------------------------------------------------
class ListActiveIntegrationsResponse(BaseModel):
    integrations: list[dict]


# ---------------------------------------------------------------------------
# /internal/microsoft/ensure-subscription — keep Graph subscriptions alive
# ---------------------------------------------------------------------------
class EnsureSubscriptionRequest(BaseModel):
    user_id: str
    org_id: str
    resource: str = "communications/callRecords"


class EnsureSubscriptionResponse(BaseModel):
    subscription_id: str
    expiration: str
    action: str  # 'created' | 'renewed' | 'noop'


@router.post(
    "/microsoft/ensure-subscription",
    response_model=EnsureSubscriptionResponse,
    dependencies=[Depends(require_internal_token)],
)
async def ensure_microsoft_subscription(
    body: EnsureSubscriptionRequest,
    session: Session = Depends(get_db),
) -> EnsureSubscriptionResponse:
    """Idempotent — creates a subscription if none exists for this user/resource
    or renews one that's within 24h of expiring.

    Call weekly/nightly from the Inngest cron; the 4230-min expiry window
    means we must renew within ~2.9 days of creation.
    """
    import secrets
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from app.integrations.teams.graph_client import GraphAPIClient
    from app.services.oauth_tokens import get_valid_access_token

    org_uuid = UUID(body.org_id)
    user_uuid = UUID(body.user_id)
    now = datetime.now(UTC)
    renewal_threshold = now + timedelta(hours=24)

    access_token = await get_valid_access_token(
        session,
        org_id=org_uuid,
        user_id=user_uuid,
        platform="microsoft",
    )

    existing = session.scalar(
        select(GraphSubscription)
        .where(GraphSubscription.user_id == str(user_uuid))
        .where(GraphSubscription.resource == body.resource)
        .where(GraphSubscription.is_active.is_(True))
        .limit(1)
    )

    notification_url = (
        f"{(settings.public_api_url or '').rstrip('/')}/api/v1/webhooks/teams"
    )
    client_state = settings.microsoft_webhook_secret or secrets.token_urlsafe(32)

    graph = GraphAPIClient()

    if existing is not None:
        expiration_iso = existing.expiration
        expiration_dt = datetime.fromisoformat(expiration_iso.replace("Z", "+00:00"))
        if expiration_dt > renewal_threshold:
            return EnsureSubscriptionResponse(
                subscription_id=existing.id,
                expiration=expiration_iso,
                action="noop",
            )
        try:
            renewed = await graph.renew_subscription(
                access_token, existing.id, expiration_minutes=4230
            )
            existing.expiration = renewed["expirationDateTime"]
            session.flush()
            return EnsureSubscriptionResponse(
                subscription_id=existing.id,
                expiration=renewed["expirationDateTime"],
                action="renewed",
            )
        except Exception as exc:
            logger.exception("graph_subscription_renew_failed id=%s", existing.id)
            # Deactivate so the next run re-creates.
            existing.is_active = False
            session.flush()
            del exc  # flow through to create

    created = await graph.subscribe_to_call_records(
        access_token,
        notification_url=notification_url,
        client_state=client_state,
    )
    created_id = created["id"]
    sub = session.get(GraphSubscription, created_id)
    if sub is not None:
        sub.org_id = str(org_uuid)
        sub.user_id = str(user_uuid)
        sub.resource = body.resource
        sub.client_state = client_state
        sub.notification_url = notification_url
        sub.expiration = created["expirationDateTime"]
        sub.is_active = True
    else:
        session.add(
            GraphSubscription(
                id=created_id,
                org_id=str(org_uuid),
                user_id=str(user_uuid),
                resource=body.resource,
                client_state=client_state,
                notification_url=notification_url,
                expiration=created["expirationDateTime"],
                is_active=True,
            )
        )
    session.flush()
    return EnsureSubscriptionResponse(
        subscription_id=created_id,
        expiration=created["expirationDateTime"],
        action="created",
    )


@router.get(
    "/calendar/list-active-integrations",
    response_model=ListActiveIntegrationsResponse,
    dependencies=[Depends(require_internal_token)],
)
async def list_active_integrations(
    session: Session = Depends(get_db),
) -> ListActiveIntegrationsResponse:
    """Return every active ``(org_id, user_id, platform)`` tuple so the
    Inngest cron can fan out one sync event per connection.
    """
    rows = session.scalars(
        select(IntegrationCredential)
        .where(IntegrationCredential.is_active.is_(True))
        .where(
            IntegrationCredential.platform.in_(["zoom", "microsoft", "google"])
        )
    ).all()
    return ListActiveIntegrationsResponse(
        integrations=[
            {
                "org_id": r.org_id,
                "user_id": r.user_id,
                "platform": r.platform,
            }
            for r in rows
        ]
    )


# ---------------------------------------------------------------------------
# /internal/meeting-status — let Inngest functions flip a meeting's status
# (and record an error) as a pipeline progresses or fails.
# ---------------------------------------------------------------------------
class MeetingStatusRequest(BaseModel):
    meeting_id: str
    status: str
    error_message: str | None = None


class MeetingStatusResponse(BaseModel):
    ok: bool


@router.post(
    "/meeting-status",
    response_model=MeetingStatusResponse,
    dependencies=[Depends(require_internal_token)],
)
async def set_meeting_status(
    body: MeetingStatusRequest,
    session: Session = Depends(get_db),
) -> MeetingStatusResponse:
    meeting = session.get(Meeting, body.meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting.status = body.status
    if body.error_message is not None:
        meeting.error_message = body.error_message
    session.flush()
    return MeetingStatusResponse(ok=True)
