from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

router = APIRouter()


@router.get("/")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "dealwise-api"}


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
        checks["database"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
