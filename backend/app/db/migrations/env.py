"""Alembic environment — drives migrations against the worker SQLite engine."""

from __future__ import annotations

from alembic import context

# Register models on the metadata for autogenerate.
import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.engine import get_engine

target_metadata = Base.metadata


def _include_name(name, type_, parent_names) -> bool:  # noqa: ANN001
    """Exclude sqlite-vec's vec0 virtual table (and its shadow tables) from
    autogenerate / ``alembic check``. They live outside the ORM metadata
    (created via app.db.vectors.create_vec_table), so otherwise autogenerate
    would spuriously want to drop them."""
    return not (
        type_ == "table" and name is not None and name.startswith("vec_embeddings")
    )


def run_migrations_offline() -> None:
    engine = get_engine()
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        include_name=_include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite needs batch mode for ALTERs
            include_name=_include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
