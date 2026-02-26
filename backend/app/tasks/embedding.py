import asyncio
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.llm.chunking import DocumentChunker, TranscriptChunker
from app.llm.openai_provider import OpenAIEmbeddingProvider
from app.models.document import Document
from app.models.embedding import Embedding
from app.models.meeting import Meeting
from app.services.embedding_service import EmbeddingService
from app.services.transcript_service import TranscriptService
from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(base=BaseTask, bind=True, queue="embedding")
def generate_embeddings(self, meeting_id: str) -> str:
    """Chunk transcript and generate embeddings via OpenAI. Store in pgvector."""

    async def _embed():
        settings = get_settings()

        async with async_session_factory() as session:
            try:
                # Get the transcript and its segments
                transcript_svc = TranscriptService(db=session)
                transcript = await transcript_svc.get_transcript(UUID(meeting_id))
                segments = await transcript_svc.get_segments(transcript.id)

                if not segments:
                    logger.warning(
                        "generate_embeddings_no_segments",
                        meeting_id=meeting_id,
                    )
                    return

                # Convert segments to dicts for the chunker
                segment_dicts = [
                    {
                        "id": str(seg.id),
                        "text": seg.text,
                        "speaker_label": seg.speaker_label,
                        "speaker_name": seg.speaker_name,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                    }
                    for seg in segments
                ]

                # Chunk the segments
                chunker = TranscriptChunker()
                chunks = chunker.chunk_segments(segment_dicts)

                if not chunks:
                    logger.warning(
                        "generate_embeddings_no_chunks",
                        meeting_id=meeting_id,
                    )
                    return

                # Prepare chunk dicts for embed_and_store
                chunk_dicts = [
                    {
                        "text": chunk.text,
                        "source_type": chunk.source_type,
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.index,
                        "metadata": chunk.metadata,
                    }
                    for chunk in chunks
                ]

                # Get the meeting to find deal_id and org_id
                meeting_stmt = select(Meeting).where(Meeting.id == UUID(meeting_id))
                result = await session.execute(meeting_stmt)
                meeting = result.scalar_one()

                # Create embedding service and embed+store
                embedding_provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
                embedding_svc = EmbeddingService(db=session, embedding_provider=embedding_provider)
                count = await embedding_svc.embed_and_store(
                    chunks=chunk_dicts,
                    deal_id=meeting.deal_id,
                    org_id=meeting.org_id,
                )

                await session.commit()

                logger.info(
                    "generate_embeddings_complete",
                    meeting_id=meeting_id,
                    chunk_count=len(chunks),
                    embedding_count=count,
                )
            except Exception:
                await session.rollback()
                raise

    _run_async(_embed())
    return meeting_id


@celery_app.task(base=BaseTask, bind=True, queue="embedding")
def generate_document_embeddings(self, document_id: str, deal_id: str, org_id: str) -> str:
    """Extract text from document, chunk, and generate embeddings."""

    async def _embed_document():
        settings = get_settings()

        async with async_session_factory() as session:
            try:
                # Get the document
                doc_stmt = select(Document).where(Document.id == UUID(document_id))
                result = await session.execute(doc_stmt)
                document = result.scalar_one_or_none()

                if document is None:
                    raise ValueError(f"Document not found: {document_id}")

                if not document.extracted_text:
                    logger.warning(
                        "generate_document_embeddings_no_text",
                        document_id=document_id,
                    )
                    return

                # Chunk the document text
                chunker = DocumentChunker()
                chunks = chunker.chunk_text(
                    text=document.extracted_text,
                    source_id=document_id,
                )

                if not chunks:
                    logger.warning(
                        "generate_document_embeddings_no_chunks",
                        document_id=document_id,
                    )
                    return

                # Prepare chunk dicts for embed_and_store
                chunk_dicts = [
                    {
                        "text": chunk.text,
                        "source_type": chunk.source_type,
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.index,
                        "metadata": chunk.metadata,
                    }
                    for chunk in chunks
                ]

                # Create embedding service and embed+store
                embedding_provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
                embedding_svc = EmbeddingService(db=session, embedding_provider=embedding_provider)
                count = await embedding_svc.embed_and_store(
                    chunks=chunk_dicts,
                    deal_id=UUID(deal_id),
                    org_id=UUID(org_id),
                )

                await session.commit()

                logger.info(
                    "generate_document_embeddings_complete",
                    document_id=document_id,
                    deal_id=deal_id,
                    chunk_count=len(chunks),
                    embedding_count=count,
                )
            except Exception:
                await session.rollback()
                raise

    _run_async(_embed_document())
    return document_id


@celery_app.task(base=BaseTask, bind=True, queue="embedding")
def reindex_deal(self, deal_id: str) -> str:
    """Regenerate all embeddings for a deal (e.g., after model upgrade)."""

    async def _reindex():
        settings = get_settings()

        async with async_session_factory() as session:
            try:
                # Delete all existing embeddings for this deal
                delete_stmt = delete(Embedding).where(
                    Embedding.deal_id == UUID(deal_id)
                )
                result = await session.execute(delete_stmt)
                deleted_count = result.rowcount

                logger.info(
                    "reindex_deal_embeddings_deleted",
                    deal_id=deal_id,
                    deleted_count=deleted_count,
                )

                # Find all meetings in this deal
                meeting_stmt = select(Meeting).where(Meeting.deal_id == UUID(deal_id))
                meeting_result = await session.execute(meeting_stmt)
                meetings = list(meeting_result.scalars().all())

                # Find all documents in this deal
                doc_stmt = select(Document).where(Document.deal_id == UUID(deal_id))
                doc_result = await session.execute(doc_stmt)
                documents = list(doc_result.scalars().all())

                await session.commit()
            except Exception:
                await session.rollback()
                raise

        # Re-generate embeddings for all meetings
        for meeting in meetings:
            try:
                async with async_session_factory() as session:
                    try:
                        transcript_svc = TranscriptService(db=session)
                        transcript = await transcript_svc.get_transcript(meeting.id)
                        segments = await transcript_svc.get_segments(transcript.id)

                        if not segments:
                            continue

                        segment_dicts = [
                            {
                                "id": str(seg.id),
                                "text": seg.text,
                                "speaker_label": seg.speaker_label,
                                "speaker_name": seg.speaker_name,
                                "start_time": seg.start_time,
                                "end_time": seg.end_time,
                            }
                            for seg in segments
                        ]

                        chunker = TranscriptChunker()
                        chunks = chunker.chunk_segments(segment_dicts)

                        if not chunks:
                            continue

                        chunk_dicts = [
                            {
                                "text": chunk.text,
                                "source_type": chunk.source_type,
                                "source_id": chunk.source_id,
                                "chunk_index": chunk.index,
                                "metadata": chunk.metadata,
                            }
                            for chunk in chunks
                        ]

                        embedding_provider = OpenAIEmbeddingProvider(
                            api_key=settings.openai_api_key
                        )
                        embedding_svc = EmbeddingService(
                            db=session, embedding_provider=embedding_provider
                        )
                        await embedding_svc.embed_and_store(
                            chunks=chunk_dicts,
                            deal_id=meeting.deal_id,
                            org_id=meeting.org_id,
                        )

                        await session.commit()

                        logger.info(
                            "reindex_deal_meeting_complete",
                            deal_id=deal_id,
                            meeting_id=str(meeting.id),
                            chunk_count=len(chunks),
                        )
                    except Exception:
                        await session.rollback()
                        raise
            except Exception:
                logger.warning(
                    "reindex_deal_meeting_skipped",
                    deal_id=deal_id,
                    meeting_id=str(meeting.id),
                    reason="no_transcript_or_error",
                )

        # Re-generate embeddings for all documents
        for document in documents:
            try:
                if not document.extracted_text:
                    continue

                async with async_session_factory() as session:
                    try:
                        chunker = DocumentChunker()
                        chunks = chunker.chunk_text(
                            text=document.extracted_text,
                            source_id=str(document.id),
                        )

                        if not chunks:
                            continue

                        chunk_dicts = [
                            {
                                "text": chunk.text,
                                "source_type": chunk.source_type,
                                "source_id": chunk.source_id,
                                "chunk_index": chunk.index,
                                "metadata": chunk.metadata,
                            }
                            for chunk in chunks
                        ]

                        embedding_provider = OpenAIEmbeddingProvider(
                            api_key=settings.openai_api_key
                        )
                        embedding_svc = EmbeddingService(
                            db=session, embedding_provider=embedding_provider
                        )
                        await embedding_svc.embed_and_store(
                            chunks=chunk_dicts,
                            deal_id=document.deal_id,
                            org_id=document.org_id,
                        )

                        await session.commit()

                        logger.info(
                            "reindex_deal_document_complete",
                            deal_id=deal_id,
                            document_id=str(document.id),
                            chunk_count=len(chunks),
                        )
                    except Exception:
                        await session.rollback()
                        raise
            except Exception:
                logger.warning(
                    "reindex_deal_document_skipped",
                    deal_id=deal_id,
                    document_id=str(document.id),
                    reason="no_text_or_error",
                )

        logger.info(
            "reindex_deal_complete",
            deal_id=deal_id,
            meeting_count=len(meetings),
            document_count=len(documents),
        )

    _run_async(_reindex())
    return deal_id
