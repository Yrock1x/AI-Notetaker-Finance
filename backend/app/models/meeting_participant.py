import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin


class MeetingParticipant(BaseMixin, Base):
    __tablename__ = "meeting_participants"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # e.g., "Speaker 0", "Speaker 1"
    speaker_name: Mapped[str | None] = mapped_column(String(255))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    # Relationships
    meeting = relationship("Meeting", back_populates="participants")
