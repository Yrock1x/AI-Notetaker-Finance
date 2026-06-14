"""add profiles.password_hash for local email/password accounts

Adds a nullable credential column to ``profiles``. OAuth-only users keep
``NULL``; email/password accounts store an Argon2id hash. The fresh-DB path
(init_schema → create_all) already picks this up from the model — this migration
exists for databases created at 0001 (e.g. the Fly.io volume).

Revision ID: 0002_password_hash
Revises: 0001_initial
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_password_hash"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(bind) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns("profiles")}


def upgrade() -> None:
    # 0001 materializes the schema from the ORM models via create_all, so on a
    # FRESH database the column already exists (the model now declares it) and
    # this migration is a no-op. On a database created at 0001 *before* the
    # model carried password_hash (the live Fly.io volume), it adds the column.
    bind = op.get_bind()
    if "password_hash" not in _columns(bind):
        op.add_column("profiles", sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if "password_hash" in _columns(bind):
        # SQLite needs batch mode to drop a column on older engines.
        with op.batch_alter_table("profiles") as batch_op:
            batch_op.drop_column("password_hash")
