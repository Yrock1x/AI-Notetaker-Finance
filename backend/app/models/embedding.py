import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # type: ignore[assignment, misc]

EMBEDDING_DIMENSIONS = 1536


class Embedding(OrgScopedMixin, Base):
    __tablename__ = "embeddings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # transcript_segment, document_chunk
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding = mapped_column(
        Vector(EMBEDDING_DIMENSIONS) if Vector else None,
        nullable=True,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    def __repr__(self) -> str:
        return f"<Embedding {self.source_type}:{self.source_id} chunk={self.chunk_index}>"
