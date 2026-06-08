"""Schema creation helper — single source of truth for both Alembic and tests.

``init_schema`` builds every ORM table plus the vec0 virtual table on a fresh
database. The initial Alembic migration and the test fixtures both call it, so
the schema is defined in exactly one place (the models).
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.engine import get_engine
from app.db.vectors import create_vec_table

# Importing models registers them on Base.metadata.
import app.db.models  # noqa: F401


def init_schema(engine: Engine | None = None) -> None:
    """Create all tables + the vec0 virtual table (idempotent)."""
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        create_vec_table(conn)
