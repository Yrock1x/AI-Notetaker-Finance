import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin


class Deal(OrgScopedMixin, Base):
    __tablename__ = "deals"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_company: Mapped[str | None] = mapped_column(String(255))
    deal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
    )  # m_and_a, pe, vc, debt, general
    stage: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )  # active, closed, archived
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization", back_populates="deals")
    memberships = relationship("DealMembership", back_populates="deal", lazy="noload")
    meetings = relationship("Meeting", back_populates="deal", lazy="noload")
    documents = relationship("Document", back_populates="deal", lazy="noload")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<Deal {self.name}>"
