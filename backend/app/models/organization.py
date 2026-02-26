from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin


class Organization(BaseMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    settings: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Relationships
    memberships = relationship("OrgMembership", back_populates="organization", lazy="selectin")
    deals = relationship("Deal", back_populates="organization", lazy="noload")

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"
