"""add deal_vdr_connections for CogniVault per-deal sharing

Backs the "Connect a deal to a CogniVault VDR" flow: one row per deal that has
been shared into a VDR, carrying ``vdr_id``, ``status`` (active|revoked), and the
``share_scopes`` the partner API may pull. The fresh-DB path (0001 →
``Base.metadata.create_all``) already materializes this table from the model — so
on a fresh database this migration is a no-op (``checkfirst=True``). It exists for
databases created at 0001 *before* the model carried the table (the Fly.io volume).

Revision ID: 0003_deal_vdr_connections
Revises: 0002_password_hash
Create Date: 2026-06-14
"""

from __future__ import annotations

from typing import cast

from alembic import op
from sqlalchemy import Table

# Importing models registers them on Base.metadata so __table__ is available.
import app.db.models  # noqa: F401
from app.db.models import DealVdrConnection

revision = "0003_deal_vdr_connections"
down_revision = "0002_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst=True → CREATE only if the table is missing, so this is idempotent
    # on a fresh DB (where 0001's create_all already built it).
    # ``__table__`` is typed as FromClause by the declarative stubs; it is really
    # a Table, which is what exposes create()/drop().
    cast(Table, DealVdrConnection.__table__).create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    cast(Table, DealVdrConnection.__table__).drop(op.get_bind(), checkfirst=True)
