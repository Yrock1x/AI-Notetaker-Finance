from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import EmbeddingProvider
from app.models.embedding import Embedding

logger = structlog.get_logger(__name__)


class EmbeddingService:
    def __init__(self, db: AsyncSession, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.provider = embedding_provider

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string."""
        return await self.provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of text strings."""
        return await self.provider.embed_batch(texts)

    async def store_embeddings(
        self,
        chunks: list[dict],
        vectors: list[list[float]],
        deal_id: UUID,
        org_id: UUID,
    ) -> int:
        """Store embedding vectors with metadata.

        Each chunk dict should have: text, source_type, source_id, chunk_index,
        and optional metadata.
        """
        embeddings = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            embedding = Embedding(
                org_id=org_id,
                deal_id=deal_id,
                source_type=chunk["source_type"],
                source_id=chunk["source_id"],
                chunk_text=chunk["text"],
                chunk_index=chunk.get("chunk_index", 0),
                embedding=vector,
                metadata_=chunk.get("metadata", {}),
            )
            embeddings.append(embedding)

        self.db.add_all(embeddings)
        count = len(embeddings)
        await self.db.flush()
        logger.info(
            "embeddings_stored",
            count=count,
            deal_id=str(deal_id),
        )
        return count

    async def embed_and_store(
        self,
        chunks: list[dict],
        deal_id: UUID,
        org_id: UUID,
        batch_size: int = 100,
    ) -> int:
        """Embed texts and store in one step, processing in batches."""
        total = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            vectors = await self.embed_batch(texts)
            count = await self.store_embeddings(batch, vectors, deal_id, org_id)
            total += count
        return total

    async def search(
        self,
        query_text: str,
        deal_id: UUID,
        org_id: UUID,
        top_k: int = 10,
        score_threshold: float | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """Perform vector similarity search filtered by deal and org.

        Returns list of dicts with: text, source_type, source_id, chunk_index,
        metadata, score.
        """
        query_vector = await self.embed_text(query_text)

        # Build the base query using pgvector cosine distance
        stmt = (
            select(
                Embedding,
                Embedding.embedding.cosine_distance(query_vector).label("distance"),
            )
            .where(
                Embedding.deal_id == deal_id,
                Embedding.org_id == org_id,
            )
            .order_by("distance")
            .limit(top_k)
        )

        if source_type:
            stmt = stmt.where(Embedding.source_type == source_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        results = []
        for embedding, distance in rows:
            score = 1.0 - distance  # Convert distance to similarity score
            if score_threshold is not None and score < score_threshold:
                continue
            results.append({
                "text": embedding.chunk_text,
                "source_type": embedding.source_type,
                "source_id": str(embedding.source_id),
                "chunk_index": embedding.chunk_index,
                "metadata": embedding.metadata_ or {},
                "score": score,
            })

        logger.info(
            "vector_search",
            deal_id=str(deal_id),
            results=len(results),
            top_score=results[0]["score"] if results else None,
        )
        return results

    async def delete_embeddings_for_source(
        self, source_type: str, source_id: UUID
    ) -> int:
        """Delete all embeddings for a specific source."""
        stmt = delete(Embedding).where(
            Embedding.source_type == source_type,
            Embedding.source_id == source_id,
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        count = result.rowcount
        logger.info(
            "embeddings_deleted",
            source_type=source_type,
            source_id=str(source_id),
            count=count,
        )
        return count

    async def delete_embeddings_for_meeting(self, meeting_id: UUID) -> int:
        """Delete all embedding vectors associated with a meeting's transcript segments."""
        # Segments are stored with source_type='transcript_segment'
        # We need to find segments belonging to this meeting and delete their embeddings
        from app.models.transcript_segment import TranscriptSegment

        segment_ids_stmt = select(TranscriptSegment.id).where(
            TranscriptSegment.meeting_id == meeting_id
        )
        stmt = delete(Embedding).where(
            Embedding.source_type == "transcript_segment",
            Embedding.source_id.in_(segment_ids_stmt),
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def delete_embeddings_for_document(self, document_id: UUID) -> int:
        """Delete all embedding vectors associated with a document."""
        return await self.delete_embeddings_for_source("document_chunk", document_id)
