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
from app.dependencies import get_service_supabase
from app.integrations.deepgram.client import DeepgramClient
from app.integrations.deepgram.processor import DiarizationProcessor
from app.integrations.recall.client import RecallClient
from app.llm.chunking import DocumentChunker, TranscriptChunker
from app.llm.fireworks_provider import (
    FireworksEmbeddingProvider,
    FireworksProvider,
)
from app.llm.router import LLMRouter
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


def _llm_router() -> LLMRouter:
    r = LLMRouter()
    if settings.fireworks_api_key:
        r.register_provider("fireworks", FireworksProvider(settings.fireworks_api_key))
        r.register_embedding_provider(
            "fireworks", FireworksEmbeddingProvider(settings.fireworks_api_key)
        )
    if settings.premium_llm_enabled and settings.anthropic_api_key:
        from app.llm.anthropic_provider import AnthropicProvider  # type: ignore

        r.register_provider("anthropic", AnthropicProvider(settings.anthropic_api_key))
    return r


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

    llm = _llm_router()
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

    svc = AnalysisService(supabase=supabase, llm_router=_llm_router())
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

    llm = _llm_router()
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
    # nowhere to land and the Live panel can't subscribe.
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
                    "status": "recording",
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
    else:
        # Flip the existing meeting to 'recording' so the Live tab shows.
        supabase.table("meetings").update({"status": "recording"}).eq(
            "id", meeting_id
        ).execute()

    if not settings.recall_api_key:
        raise HTTPException(status_code=500, detail="RECALL_API_KEY not configured")
    recall = RecallClient(api_key=settings.recall_api_key)

    bot_data = await recall.create_bot(
        meeting_url=session["meeting_url"],
        bot_name="Deal Companion Notetaker",
        recording_config={
            "transcript": {"provider": {"deepgram_streaming": {}}},
        },
        metadata={
            "session_id": session["id"],
            "org_id": session["org_id"],
            "deal_id": session["deal_id"],
            "meeting_id": meeting_id,
        },
    )

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
            recall = RecallClient(api_key=settings.recall_api_key)
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
    """Download a Zoom cloud recording into Supabase Storage.

    Note: this can't create a ``meetings`` row because we don't know which
    deal it belongs to — downstream attribution is a product decision.
    Returns the file_key instead so an operator can link it by hand.
    """
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(
                body.download_url,
                headers=(
                    {"Authorization": f"Bearer {settings.zoom_client_secret}"}
                    if settings.zoom_client_secret
                    else {}
                ),
                follow_redirects=True,
            )
            resp.raise_for_status()
            file_bytes = resp.content
    except Exception as exc:
        logger.exception("zoom_ingest_download_failed")
        raise HTTPException(status_code=502, detail=f"Zoom download failed: {exc}") from exc

    file_key = f"zoom-unlinked/{body.zoom_meeting_id}.mp4"
    supabase.storage.from_(MEETINGS_BUCKET).upload(
        file_key, file_bytes, {"content-type": "video/mp4", "upsert": "true"}
    )
    logger.info(
        "zoom_recording_stored zoom_meeting_id=%s file_key=%s bytes=%d",
        body.zoom_meeting_id,
        file_key,
        len(file_bytes),
    )
    return ZoomIngestResponse(meeting_id=None, status="stored_unlinked")


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
    cred_rows = (
        supabase.table("integration_credentials")
        .select("org_id, user_id, access_token_encrypted")
        .eq("platform", "teams")
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

    from cryptography.fernet import Fernet

    if not settings.token_encryption_key:
        raise HTTPException(
            status_code=500, detail="TOKEN_ENCRYPTION_KEY not configured"
        )
    fernet = Fernet(settings.token_encryption_key.encode())
    access_token = fernet.decrypt(
        cred_rows[0]["access_token_encrypted"].encode()
    ).decode()

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

    logger.info(
        "teams_call_record_fetched call_record_id=%s organizer=%s participants=%d",
        body.call_record_id,
        organizer,
        len(participants),
    )
    return TeamsIngestResponse(
        call_record_id=body.call_record_id,
        organizer=organizer,
        participant_count=len(participants),
        handled=True,
    )


# ---------------------------------------------------------------------------
# /internal/outlook/sync-all
# ---------------------------------------------------------------------------
class OutlookSyncResponse(BaseModel):
    dispatched: int


@router.post(
    "/outlook/sync-all",
    response_model=OutlookSyncResponse,
    dependencies=[Depends(require_internal_token)],
)
async def outlook_sync_all(
    supabase: Client = Depends(get_service_supabase),
) -> OutlookSyncResponse:
    """Fan-out placeholder — once OAuth is reimplemented on Supabase (Phase 5
    of the migration plan) this will iterate ``integration_credentials``
    where platform='outlook' and is_active=true, and for each run a calendar
    delta sync. For now we just count how many credentials exist so callers
    know the cron is alive."""
    rows = (
        supabase.table("integration_credentials")
        .select("id")
        .eq("platform", "outlook")
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    return OutlookSyncResponse(dispatched=len(rows))
