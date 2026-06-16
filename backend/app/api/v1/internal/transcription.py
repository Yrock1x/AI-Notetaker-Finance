"""/internal/* — Transcription, embedding, analysis, and document processing."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.internal._common import (
    DOCUMENTS_BUCKET,
    MEETINGS_BUCKET,
    _mimetype_for_key,
    require_internal_token,
)
from app.core.config import settings
from app.db.deps import get_db
from app.db.models import (
    Document,
    Embedding,
    Meeting,
    Transcript,
    TranscriptSegment,
)
from app.db.vectors import delete_vectors, upsert_vector
from app.dependencies import get_llm_router
from app.integrations.deepgram.client import DeepgramClient
from app.integrations.deepgram.processor import DiarizationProcessor
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

    pairs = list(zip(chunks, vectors, strict=False))
    embs = [
        Embedding(
            org_id=meeting.org_id,
            deal_id=meeting.deal_id,
            source_type="transcript_segment",
            source_id=chunk.source_id or meeting.id,
            chunk_text=chunk.text,
            chunk_index=chunk.index,
            metadata_json=chunk.metadata,
        )
        for chunk, _ in pairs
    ]
    # One flush to materialise all ids, then write the vectors — instead of a
    # flush per chunk.
    session.add_all(embs)
    session.flush()
    for emb, (_, vec) in zip(embs, pairs, strict=False):
        upsert_vector(
            session, embedding_id=emb.id, deal_id=meeting.deal_id, vector=vec
        )

    return EmbedResponse(count=len(embs))


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
    # Commit the extracted text before the embedding network call below so the
    # single SQLite writer lock isn't held across llm.embed_batch (which would
    # stall the live-transcript write path).
    session.commit()

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

    pairs = list(zip(chunks, vectors, strict=False))
    embs = [
        Embedding(
            org_id=doc.org_id,
            deal_id=doc.deal_id,
            source_type="document_chunk",
            source_id=doc.id,
            chunk_text=c.text,
            chunk_index=c.index,
            metadata_json=c.metadata,
        )
        for c, _ in pairs
    ]
    # One flush to materialise all ids, then write the vectors — instead of a
    # flush per chunk.
    session.add_all(embs)
    session.flush()
    for emb, (_, vec) in zip(embs, pairs, strict=False):
        upsert_vector(
            session, embedding_id=emb.id, deal_id=doc.deal_id, vector=vec
        )

    return ProcessDocumentResponse(embedding_count=len(embs))


