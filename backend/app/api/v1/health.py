"""Worker health + readiness endpoints."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def health_check() -> dict:
    """Liveness — returns 200 once the process is up."""
    return {"status": "healthy", "service": "cognisuite-worker"}


@router.get("/ready", response_model=None)
async def readiness_check() -> dict | JSONResponse:
    """Readiness — verifies Supabase reachability.

    The worker is ready when it can hit the Supabase Auth health endpoint.
    Anything else (LLM / Deepgram / Recall) is external; we don't fail
    readiness on those because they're not in the request path for every
    endpoint.
    """
    checks: dict[str, str] = {}

    if settings.supabase_url:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(
                    f"{settings.supabase_url.rstrip('/')}/auth/v1/health"
                )
                checks["supabase"] = "ok" if resp.status_code < 500 else "degraded"
        except Exception as e:  # noqa: BLE001
            logger.error("readiness_check_supabase: %s", e)
            checks["supabase"] = "error"
    else:
        checks["supabase"] = "not_configured"

    has_errors = any(v == "error" for v in checks.values())
    if has_errors:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "checks": checks},
        )
    return {"status": "ready", "checks": checks}
