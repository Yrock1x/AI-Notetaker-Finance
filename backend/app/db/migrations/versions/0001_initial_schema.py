"""initial SQLite schema (consolidated from supabase/migrations 0001..0011)

Builds every table from the ORM models plus the vec0 virtual table. Models stay
the single source of truth — this migration just materializes them.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-07
"""

from __future__ import annotations

from alembic import op

# Importing models registers them on Base.metadata.
import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.vectors import create_vec_table

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    create_vec_table(bind)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TABLE IF EXISTS vec_embeddings")
    Base.metadata.drop_all(bind)
