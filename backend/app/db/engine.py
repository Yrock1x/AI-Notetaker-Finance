"""SQLite engine + session for the worker-owned database.

Synchronous SQLAlchemy on the stdlib sqlite3 driver. Sync (not aiosqlite) on
purpose: (a) loading the sqlite-vec extension is reliable on a real sqlite3
connection, and (b) it matches the existing codebase, which already calls its
(synchronous) Supabase store from inside async FastAPI handlers. SQLite in WAL
mode serves many concurrent readers; writes serialize, which suits our workload
(the only hot writer is the live-transcript path).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import sqlite_vec
import structlog
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = structlog.get_logger(__name__)

# On Fly.io this points at the attached volume, e.g. /data/app.db.
DEFAULT_DB_PATH = os.getenv("SQLITE_DB_PATH", "/data/app.db")


def _sqlite_url(db_path: str) -> str:
    return f"sqlite+pysqlite:///{db_path}"


def _configure_connection(dbapi_connection, _record) -> None:  # noqa: ANN001
    """Load sqlite-vec and set pragmas on every new connection."""
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)

    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def create_db_engine(db_path: str | None = None) -> Engine:
    """Build an Engine with sqlite-vec + WAL configured per connection.

    ``check_same_thread=False`` lets pooled connections cross FastAPI's
    threadpool workers; each thread still uses its own pooled connection.
    """
    path = db_path or DEFAULT_DB_PATH
    engine = create_engine(
        _sqlite_url(path),
        future=True,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _configure_connection)
    logger.info("sqlite_engine_created", path=path)
    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), class_=Session, expire_on_commit=False, future=True
        )
    return _session_factory


def configure_engine(engine: Engine) -> None:
    """Override the global engine/session factory (used by tests)."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(
        bind=engine, class_=Session, expire_on_commit=False, future=True
    )


def get_db() -> Iterator[Session]:
    """FastAPI dependency: a transactional session (commit on success)."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
