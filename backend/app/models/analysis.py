import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin


class Analysis(OrgScopedMixin, Base):
    __tablename__ = "analyses"

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
        index=True,
    )
    call_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # diligence, management_presentation, buyer_call, financial_review, qoe, general
    structured_output: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    grounding_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",
    )  # running, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    meeting = relationship("Meeting", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<Analysis {self.call_type} v{self.version} [{self.status}]>"
