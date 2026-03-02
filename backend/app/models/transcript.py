import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin


class Transcript(OrgScopedMixin, Base):
    __tablename__ = "transcripts"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    deepgram_response: Mapped[dict | None] = mapped_column(JSONB)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    # Relationships
    meeting = relationship("Meeting", back_populates="transcript")
    segments = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        lazy="noload",
        order_by="TranscriptSegment.segment_index",
    )

    def __repr__(self) -> str:
        return f"<Transcript meeting={self.meeting_id} words={self.word_count}>"
