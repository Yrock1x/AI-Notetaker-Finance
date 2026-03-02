import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin


class Meeting(OrgScopedMixin, Base):
    __tablename__ = "meetings"

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
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="upload",
    )  # upload, zoom, teams, bot, slack
    source_url: Mapped[str | None] = mapped_column(String(2048))
    file_key: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="uploading",
    )  # uploading, transcribing, analyzing, ready, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Relationships
    deal = relationship("Deal", back_populates="meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting", lazy="noload")
    transcript = relationship("Transcript", back_populates="meeting", uselist=False, lazy="noload")
    analyses = relationship("Analysis", back_populates="meeting", lazy="noload")

    def __repr__(self) -> str:
        return f"<Meeting {self.title} [{self.status}]>"
