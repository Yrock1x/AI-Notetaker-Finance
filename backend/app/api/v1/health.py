import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "deal-companion-api"}


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Readiness check — verifies database connectivity."""
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error("readiness_check_failed: database - %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"},
        )

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


@router.get("/debug-deals")
async def debug_deals(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Temporary debug endpoint to test deals query directly."""
    from app.core.config import settings
    if not settings.demo_mode:
        return {"error": "only available in demo mode"}
    try:
        result = await db.execute(
            text("SELECT id, name, status FROM deals LIMIT 5")
        )
        rows = [{"id": str(r[0]), "name": r[1], "status": r[2]} for r in result.fetchall()]
        return {"deals": rows, "code_version": "v2-debug"}
    except Exception as e:
        return {"error": str(e), "code_version": "v2-debug"}
