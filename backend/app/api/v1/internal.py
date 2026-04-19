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
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from app.core.config import settings
from app.dependencies import get_llm_router, get_service_supabase
from app.integrations.deepgram.client import DeepgramClient
from app.integrations.deepgram.processor import DiarizationProcessor
from app.integrations.recall.client import RecallClient
from app.llm.chunking import DocumentChunker, TranscriptChunker
from app.services.analysis_service import AnalysisService
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
    supabase: Client = Depends(get_service_supabase),
) -> TranscribeResponse:
    """Call Deepgram on the meeting's uploaded audio file, write transcript +
    segments, return counts."""
    meeting_rows = (
        supabase.table("meetings")
        .select("id, org_id, file_key, status")
        .eq("id", body.meeting_id)
        .limit(1)
        .execute()
        .data
    )
    if not meeting_rows:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting = meeting_rows[0]
    file_key = meeting.get("file_key")
    if not file_key:
        raise HTTPException(status_code=400, detail="Meeting has no file_key")

    # Signed URL for Deepgram to pull the file. One hour is plenty.
    signed = supabase.storage.from_(MEETINGS_BUCKET).create_signed_url(
        file_key, expires_in=3600
    )
    audio_url = signed.get("signedURL") or signed.get("signed_url")
    if not audio_url:
        raise HTTPException(
            status_code=502, detail="Could not sign meeting storage URL"
        )

    if not settings.deepgram_api_key:
        raise HTTPException(
            status_code=500, detail="DEEPGRAM_API_KEY is not configured"
        )
    dg = DeepgramClient(api_key=settings.deepgram_api_key)
    deepgram_response = await dg.transcribe_file(audio_url)

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

    transcript_row = {
        "org_id": meeting["org_id"],
        "meeting_id": meeting["id"],
        "full_text": " ".join(full_text_parts),
        "language": "en",
        "deepgram_response": deepgram_response,
        "word_count": word_count,
        "confidence_score": (conf_sum / conf_n) if conf_n else None,
    }
    transcript = (
        supabase.table("transcripts")
        .upsert(transcript_row, on_conflict="meeting_id")
        .execute()
        .data[0]
    )

    # Insert segment rows. Delete any prior finalized segments first so a
    # re-run doesn't duplicate; live-streamed partials are untouched and
    # will be replaced by matching recall_segment_id upserts when the bot
    # finishes.
    supabase.table("transcript_segments").delete().eq(
        "meeting_id", meeting["id"]
    ).eq("is_partial", False).execute()

    if segments:
        segment_rows = [
            {
                "transcript_id": transcript["id"],
                "meeting_id": meeting["id"],
                "speaker_label": seg.get("speaker_label") or "Speaker",
                "speaker_name": seg.get("speaker_name"),
                "text": seg.get("text", ""),
                "start_time": float(seg.get("start_time") or 0),
                "end_time": float(seg.get("end_time") or 0),
                "confidence": seg.get("confidence"),
                "segment_index": int(seg.get("segment_index") or i),
                "is_partial": False,
            }
            for i, seg in enumerate(segments)
        ]
        supabase.table("transcript_segments").insert(segment_rows).execute()

    return TranscribeResponse(
        transcript_id=transcript["id"], segment_count=len(segments)
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
    supabase: Client = Depends(get_service_supabase),
) -> EmbedResponse:
    """Chunk the meeting's finalized transcript segments, embed with
    Fireworks, and upsert into the ``embeddings`` table."""
    meeting_rows = (
        supabase.table("meetings")
        .select("id, org_id, deal_id")
        .eq("id", body.meeting_id)
        .limit(1)
        .execute()
        .data
    )
    if not meeting_rows:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting = meeting_rows[0]

    segments = (
        supabase.table("transcript_segments")
        .select("id, speaker_label, speaker_name, text, start_time, end_time")
        .eq("meeting_id", meeting["id"])
        .eq("is_partial", False)
        .order("start_time")
        .execute()
        .data
        or []
    )
    if not segments:
        return EmbedResponse(count=0)

    chunker = TranscriptChunker()
    chunks = chunker.chunk_segments(segments)
    if not chunks:
        return EmbedResponse(count=0)

    llm = get_llm_router()
    vectors = await llm.embed_batch([c.text for c in chunks])

    rows: list[dict[str, Any]] = []
    for chunk, vec in zip(chunks, vectors, strict=False):
        rows.append(
            {
                "org_id": meeting["org_id"],
                "deal_id": meeting["deal_id"],
                "source_type": "transcript_segment",
                "source_id": chunk.source_id or meeting["id"],
                "chunk_text": chunk.text,
                "chunk_index": chunk.index,
                "embedding": vec,
                "metadata": chunk.metadata,
            }
        )

    # Clear prior embeddings for this meeting's segments, then insert fresh.
    segment_ids = [s["id"] for s in segments]
    supabase.table("embeddings").delete().in_(
        "source_id", segment_ids
    ).eq("source_type", "transcript_segment").execute()
    supabase.table("embeddings").insert(rows).execute()

    return EmbedResponse(count=len(rows))


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
    supabase: Client = Depends(get_service_supabase),
) -> AnalyzeResponse:
    meeting_rows = (
        supabase.table("meetings")
        .select("id, org_id")
        .eq("id", body.meeting_id)
        .limit(1)
        .execute()
        .data
    )
    if not meeting_rows:
        raise HTTPException(status_code=404, detail="Meeting not found")
    meeting = meeting_rows[0]

    svc = AnalysisService(supabase=supabase, llm_router=get_llm_router())
    result = await svc.run_analysis(
        meeting_id=uuid.UUID(meeting["id"]),
        org_id=uuid.UUID(meeting["org_id"]),
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
    supabase: Client = Depends(get_service_supabase),
) -> ProcessDocumentResponse:
    """Download a deal document from Supabase Storage, extract text, chunk,
    embed, and upsert into ``embeddings``."""
    doc_rows = (
        supabase.table("documents")
        .select("id, org_id, deal_id, file_key, document_type")
        .eq("id", body.document_id)
        .limit(1)
        .execute()
        .data
    )
    if not doc_rows:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = doc_rows[0]

    download = supabase.storage.from_(DOCUMENTS_BUCKET).download(doc["file_key"])
    file_bytes = bytes(download)

    dtype = (doc.get("document_type") or "").lower()
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
        supabase.table("documents").update({"extracted_text": ""}).eq(
            "id", doc["id"]
        ).execute()
        return ProcessDocumentResponse(embedding_count=0)

    supabase.table("documents").update({"extracted_text": extracted}).eq(
        "id", doc["id"]
    ).execute()

    chunker = DocumentChunker()
    chunks = chunker.chunk_text(extracted, source_id=doc["id"])
    if not chunks:
        return ProcessDocumentResponse(embedding_count=0)

    llm = get_llm_router()
    vectors = await llm.embed_batch([c.text for c in chunks])

    # Wipe any prior embeddings for this document first.
    supabase.table("embeddings").delete().eq("source_type", "document_chunk").eq(
        "source_id", doc["id"]
    ).execute()

    rows = [
        {
            "org_id": doc["org_id"],
            "deal_id": doc["deal_id"],
            "source_type": "document_chunk",
            "source_id": doc["id"],
            "chunk_text": c.text,
            "chunk_index": c.index,
            "embedding": v,
            "metadata": c.metadata,
        }
        for c, v in zip(chunks, vectors, strict=False)
    ]
    supabase.table("embeddings").insert(rows).execute()
    return ProcessDocumentResponse(embedding_count=len(rows))


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
    supabase: Client = Depends(get_service_supabase),
) -> BotResponse:
    # Fail fast before touching the DB — if the Recall key is missing, the
    # call can never succeed and Inngest would otherwise keep retrying while
    # leaving the meeting row in a half-populated 'recording' state.
    if not settings.recall_api_key:
        raise HTTPException(status_code=500, detail="RECALL_API_KEY not configured")

    sess_rows = (
        supabase.table("meeting_bot_sessions")
        .select("*")
        .eq("id", body.session_id)
        .limit(1)
        .execute()
        .data
    )
    if not sess_rows:
        raise HTTPException(status_code=404, detail="Bot session not found")
    session = sess_rows[0]

    # Ensure a meetings row exists — without one, live-transcript writes have
    # nowhere to land and the Live panel can't subscribe. Leave status as
    # 'scheduled'; the Recall status webhook flips it to 'recording' only
    # once the bot is actually in-call.
    meeting_id = session.get("meeting_id")
    if not meeting_id:
        platform_source_map = {
            "zoom": "zoom",
            "teams": "teams",
            "google_meet": "meet",
        }
        new_meeting = (
            supabase.table("meetings")
            .insert(
                {
                    "org_id": session["org_id"],
                    "deal_id": session["deal_id"],
                    "title": f"Live meeting — {session['platform']}",
                    "source": platform_source_map.get(
                        session["platform"], "upload"
                    ),
                    "source_url": session["meeting_url"],
                    "status": "scheduled",
                    "created_by": session["created_by"],
                }
            )
            .execute()
            .data[0]
        )
        meeting_id = new_meeting["id"]
        supabase.table("meeting_bot_sessions").update(
            {"meeting_id": meeting_id}
        ).eq("id", session["id"]).execute()

    recall = RecallClient(api_key=settings.recall_api_key, region=settings.recall_region)

    try:
        bot_data = await recall.create_bot(
            meeting_url=session["meeting_url"],
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
            },
            metadata={
                "session_id": session["id"],
                "org_id": session["org_id"],
                "deal_id": session["deal_id"],
                "meeting_id": meeting_id,
            },
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        logger.error(
            "recall_create_bot_failed session_id=%s status=%s body=%s",
            session["id"],
            exc.response.status_code,
            detail,
        )
        supabase.table("meeting_bot_sessions").update({"status": "failed"}).eq(
            "id", session["id"]
        ).execute()
        raise HTTPException(
            status_code=502,
            detail=f"Recall.ai rejected bot create ({exc.response.status_code}): {detail}",
        ) from exc
    except Exception as exc:
        logger.exception("recall_create_bot_error session_id=%s", session["id"])
        supabase.table("meeting_bot_sessions").update({"status": "failed"}).eq(
            "id", session["id"]
        ).execute()
        raise HTTPException(status_code=502, detail=f"Recall.ai call failed: {exc}") from exc

    recall_bot_id = bot_data.get("id")
    supabase.table("meeting_bot_sessions").update(
        {
            "status": "joining",
            "recall_bot_id": recall_bot_id,
            "live_transcript_channel": f"transcripts:{meeting_id}",
        }
    ).eq("id", session["id"]).execute()

    return BotResponse(
        session_id=session["id"], status="joining", recall_bot_id=recall_bot_id
    )


@router.post(
    "/bot/stop",
    response_model=BotResponse,
    dependencies=[Depends(require_internal_token)],
)
async def bot_stop(
    body: BotRequest,
    supabase: Client = Depends(get_service_supabase),
) -> BotResponse:
    sess_rows = (
        supabase.table("meeting_bot_sessions")
        .select("*")
        .eq("id", body.session_id)
        .limit(1)
        .execute()
        .data
    )
    if not sess_rows:
        raise HTTPException(status_code=404, detail="Bot session not found")
    session = sess_rows[0]

    if settings.recall_api_key and session.get("recall_bot_id"):
        try:
            recall = RecallClient(api_key=settings.recall_api_key, region=settings.recall_region)
            await recall.leave_bot(session["recall_bot_id"])
        except Exception:
            logger.exception("recall_leave_failed bot_id=%s", session["recall_bot_id"])

    new_status = "cancelled" if session["status"] in ("scheduled", "joining") else "completed"
    supabase.table("meeting_bot_sessions").update({"status": new_status}).eq(
        "id", session["id"]
    ).execute()

    return BotResponse(
        session_id=session["id"],
        status=new_status,
        recall_bot_id=session.get("recall_bot_id"),
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
    supabase: Client = Depends(get_service_supabase),
) -> ZoomIngestResponse:
    """Handle a ``recording.completed`` Zoom webhook.

    Flow:
      1. Try to attach the recording to an existing calendar-synced meeting
         (match on ``external_provider='zoom'`` + ``external_event_id``).
      2. If none, create an unassigned ``meetings`` row so the user can
         associate it with a deal from the calendar page.
      3. Download the recording into Supabase Storage using any active
         Zoom OAuth credential in the org (best-effort).
      4. Fire ``meeting/uploaded`` so the post-meeting pipeline runs.
    """
    from app.services.oauth_tokens import decrypt_token

    zoom_meeting_id = str(body.zoom_meeting_id)

    # 1) Attribution: find an existing meetings row for this external event.
    match = (
        supabase.table("meetings")
        .select("id, org_id, deal_id")
        .eq("external_provider", "zoom")
        .eq("external_event_id", zoom_meeting_id)
        .limit(1)
        .execute()
        .data
        or []
    )

    if match:
        meeting = match[0]
        meeting_id = meeting["id"]
        org_id = meeting["org_id"]
        deal_id = meeting.get("deal_id") or ""
    else:
        # Create an unassigned meeting. Pick any org with an active zoom
        # credential; if we can't find one, we have nothing to bind to.
        cred_rows = (
            supabase.table("integration_credentials")
            .select("org_id, user_id")
            .eq("platform", "zoom")
            .eq("is_active", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not cred_rows:
            logger.warning(
                "zoom_ingest_no_credential zoom_meeting_id=%s", zoom_meeting_id
            )
            return ZoomIngestResponse(meeting_id=None, status="no_credential")
        org_id = cred_rows[0]["org_id"]
        created_by = cred_rows[0]["user_id"]
        new_meeting = (
            supabase.table("meetings")
            .insert(
                {
                    "org_id": org_id,
                    "deal_id": None,
                    "title": body.topic or "Zoom recording",
                    "source": "zoom",
                    "external_provider": "zoom",
                    "external_event_id": zoom_meeting_id,
                    "status": "uploading",
                    "created_by": created_by,
                }
            )
            .execute()
            .data[0]
        )
        meeting_id = new_meeting["id"]
        deal_id = ""

    # 2) Look up any active zoom credential (prefer one in the matched org).
    cred_rows = (
        supabase.table("integration_credentials")
        .select("access_token_encrypted")
        .eq("platform", "zoom")
        .eq("is_active", True)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    auth_header: dict[str, str] = {}
    if cred_rows and cred_rows[0].get("access_token_encrypted"):
        try:
            zoom_access = decrypt_token(cred_rows[0]["access_token_encrypted"])
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
    supabase.storage.from_(MEETINGS_BUCKET).upload(
        file_key, file_bytes, {"content-type": "video/mp4", "upsert": "true"}
    )

    # 4) Flip status + fire the post-meeting pipeline.
    supabase.table("meetings").update(
        {
            "file_key": file_key,
            "status": "uploaded",
            "source_url": body.download_url,
        }
    ).eq("id", meeting_id).execute()

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
    supabase: Client = Depends(get_service_supabase),
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
    cred_rows = (
        supabase.table("integration_credentials")
        .select("org_id, user_id, platform")
        .in_("platform", ["microsoft", "teams"])
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not cred_rows:
        logger.warning(
            "teams_ingest_no_credential call_record_id=%s", body.call_record_id
        )
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    cred = cred_rows[0]
    try:
        access_token = await get_valid_access_token(
            supabase,
            org_id=UUID(cred["org_id"]),
            user_id=UUID(cred["user_id"]),
            platform=cred["platform"],  # type: ignore[arg-type]
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
    meeting_row: dict | None = None
    if start_times:
        probe = start_times[0]
        # Find a 'microsoft' synced meeting in the same org within ±30 min.
        candidate = (
            supabase.table("meetings")
            .select("id, deal_id")
            .eq("org_id", cred["org_id"])
            .eq("external_provider", "microsoft")
            .gte("meeting_date", probe)
            .lte("meeting_date", probe)  # best-effort exact match
            .limit(1)
            .execute()
            .data
            or []
        )
        meeting_row = candidate[0] if candidate else None

    if meeting_row is None:
        inserted = (
            supabase.table("meetings")
            .insert(
                {
                    "org_id": cred["org_id"],
                    "deal_id": None,
                    "title": organizer and f"Teams call w/ {organizer}" or "Teams call",
                    "source": "teams",
                    "external_provider": "microsoft",
                    "external_event_id": body.call_record_id,
                    "status": "uploaded",
                    "created_by": cred["user_id"],
                }
            )
            .execute()
            .data[0]
        )
        meeting_id = inserted["id"]
    else:
        meeting_id = meeting_row["id"]
        supabase.table("meetings").update({"status": "uploaded"}).eq(
            "id", meeting_id
        ).execute()

    logger.info(
        "teams_call_record_fetched call_record_id=%s organizer=%s participants=%d meeting_id=%s",
        body.call_record_id,
        organizer,
        len(participants),
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
    supabase: Client = Depends(get_service_supabase),
) -> CalendarSyncResponse:
    """Pull upcoming events from the user's connected calendar and upsert
    them into ``meetings`` keyed on (org_id, external_provider, external_event_id).

    Synced rows land with ``deal_id = NULL`` until a user assigns one on
    the calendar page. The ``source`` column is populated based on the
    conferencing platform (zoom / teams / meet / outlook).
    """
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from app.services.oauth_tokens import Platform, get_valid_access_token

    if body.platform not in {"zoom", "microsoft", "google"}:
        raise HTTPException(400, f"Unsupported platform {body.platform}")

    org_uuid = UUID(body.org_id)
    user_uuid = UUID(body.user_id)
    now = datetime.now(UTC)
    time_max = now + timedelta(days=body.lookahead_days)

    access_token = await get_valid_access_token(
        supabase,
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

        gcal = GoogleCalendarClient()
        events = await gcal.list_events(
            access_token, time_min=now, time_max=time_max
        )
        for ev in events:
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue  # all-day events don't have dateTime
            meet_url = GoogleCalendarClient.extract_meet_url(ev)
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("summary") or "Meeting",
                    "meeting_date": start,
                    "source": "meet" if meet_url else "upload",
                    "source_url": meet_url or ev.get("htmlLink"),
                    "external_event_id": ev.get("id"),
                    "external_provider": "google",
                    "status": "uploading",
                    "bot_enabled": bool(meet_url),
                    "created_by": str(user_uuid),
                }
            )

    upserted = 0
    if rows:
        # Upsert per-row because supabase-py can't do composite on_conflict
        # across a partial unique index cleanly; volume is low (<100/run).
        for row in rows:
            supabase.table("meetings").upsert(
                row,
                on_conflict="org_id,external_provider,external_event_id",
            ).execute()
            upserted += 1

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
    supabase: Client = Depends(get_service_supabase),
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
        supabase,
        org_id=org_uuid,
        user_id=user_uuid,
        platform="microsoft",
    )

    existing = (
        supabase.table("graph_subscriptions")
        .select("*")
        .eq("user_id", str(user_uuid))
        .eq("resource", body.resource)
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
        or []
    )

    notification_url = (
        f"{(settings.public_api_url or '').rstrip('/')}/api/v1/webhooks/teams"
    )
    client_state = settings.microsoft_webhook_secret or secrets.token_urlsafe(32)

    graph = GraphAPIClient()

    if existing:
        row = existing[0]
        expiration_iso = row["expiration"]
        expiration_dt = datetime.fromisoformat(expiration_iso.replace("Z", "+00:00"))
        if expiration_dt > renewal_threshold:
            return EnsureSubscriptionResponse(
                subscription_id=row["id"],
                expiration=expiration_iso,
                action="noop",
            )
        try:
            renewed = await graph.renew_subscription(
                access_token, row["id"], expiration_minutes=4230
            )
            supabase.table("graph_subscriptions").update(
                {"expiration": renewed["expirationDateTime"]}
            ).eq("id", row["id"]).execute()
            return EnsureSubscriptionResponse(
                subscription_id=row["id"],
                expiration=renewed["expirationDateTime"],
                action="renewed",
            )
        except Exception as exc:
            logger.exception("graph_subscription_renew_failed id=%s", row["id"])
            # Deactivate so the next run re-creates.
            supabase.table("graph_subscriptions").update(
                {"is_active": False}
            ).eq("id", row["id"]).execute()
            existing = []
            del exc  # flow through to create

    created = await graph.subscribe_to_call_records(
        access_token,
        notification_url=notification_url,
        client_state=client_state,
    )
    supabase.table("graph_subscriptions").upsert(
        {
            "id": created["id"],
            "org_id": str(org_uuid),
            "user_id": str(user_uuid),
            "resource": body.resource,
            "client_state": client_state,
            "notification_url": notification_url,
            "expiration": created["expirationDateTime"],
            "is_active": True,
        },
        on_conflict="id",
    ).execute()
    return EnsureSubscriptionResponse(
        subscription_id=created["id"],
        expiration=created["expirationDateTime"],
        action="created",
    )


@router.get(
    "/calendar/list-active-integrations",
    response_model=ListActiveIntegrationsResponse,
    dependencies=[Depends(require_internal_token)],
)
async def list_active_integrations(
    supabase: Client = Depends(get_service_supabase),
) -> ListActiveIntegrationsResponse:
    """Return every active ``(org_id, user_id, platform)`` tuple so the
    Inngest cron can fan out one sync event per connection.
    """
    resp = (
        supabase.table("integration_credentials")
        .select("org_id, user_id, platform")
        .eq("is_active", True)
        .in_("platform", ["zoom", "microsoft", "google"])
        .execute()
    )
    return ListActiveIntegrationsResponse(integrations=resp.data or [])
