"""Declarative base + shared column conventions for the SQLite schema.

Type mapping from the old Postgres schema:
- uuid        → TEXT, generated app-side with uuid4()
- timestamptz → TEXT, ISO-8601 UTC (lexically sortable; fills in for now())
- jsonb       → SQLAlchemy JSON (TEXT under SQLite, dict in/out)
- boolean     → INTEGER 0/1
- real        → REAL
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def gen_uuid() -> str:
    """uuid4 as a string — replaces Postgres ``gen_random_uuid()``."""
    return str(uuid.uuid4())


def utcnow_iso() -> str:
    """Current UTC time as ISO-8601 — replaces Postgres ``now()``."""
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKey:
    """Mixin: string-UUID primary key."""

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)


class Timestamps:
    """Mixin: created_at / updated_at as ISO-8601 strings.

    ``onupdate`` reproduces the old ``set_updated_at`` trigger for writes that
    go through the ORM (all writes do, post-migration).
    """

    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String, default=utcnow_iso, onupdate=utcnow_iso, nullable=False
    )


class CreatedAt:
    """Mixin: created_at only (for append-only tables)."""

    created_at: Mapped[str] = mapped_column(String, default=utcnow_iso, nullable=False)
