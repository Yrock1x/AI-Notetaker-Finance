from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin


class User(BaseMixin, Base):
    __tablename__ = "users"

    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    org_memberships = relationship("OrgMembership", back_populates="user", lazy="selectin")
    deal_memberships = relationship("DealMembership", back_populates="user", foreign_keys="[DealMembership.user_id]", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
