"""Worker health + readiness endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import get_engine
from app.db.vectors import VEC_TABLE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def health_check() -> dict:
    """Liveness — returns 200 once the process is up."""
    return {"status": "healthy", "service": "cognisuite-worker"}


@router.get("/ready", response_model=None)
async def readiness_check() -> dict | JSONResponse:
    """Readiness — verifies the worker-owned data layer is reachable.

    The worker is ready when its SQLite database answers a trivial query, the
    sqlite-vec embedding table exists, and the storage root is writable. LLM /
    Deepgram / Recall are external and not on every request path, so we don't
    fail readiness on them.
    """
    checks: dict[str, str] = {}

    # SQLite + sqlite-vec: one round-trip proves the engine, the WAL file, and
    # the loaded extension (the vec table is a vec0 virtual table).
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            # VEC_TABLE is a trusted module constant, not user input.
            conn.execute(text(f"SELECT count(*) FROM {VEC_TABLE}"))  # noqa: S608
        checks["sqlite"] = "ok"
    except Exception as e:  # noqa: BLE001
        logger.error("readiness_check_sqlite: %s", e)
        checks["sqlite"] = "error"

    # Storage: confirm the object-storage root exists and is writable.
    try:
        root = settings.storage_root
        os.makedirs(root, exist_ok=True)
        checks["storage"] = "ok" if os.access(root, os.W_OK) else "error"
    except Exception as e:  # noqa: BLE001
        logger.error("readiness_check_storage: %s", e)
        checks["storage"] = "error"

    has_errors = any(v == "error" for v in checks.values())
    if has_errors:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "checks": checks},
        )
    return {"status": "ready", "checks": checks}
