import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import async_session_factory
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def get_task_session(org_id: str | None = None) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for Celery tasks with optional RLS context.

    Unlike the request-scoped get_db dependency, this creates a standalone session
    for background task use. If org_id is provided, sets the RLS context variable.
    """
    async with async_session_factory() as session:
        try:
            if org_id:
                await session.execute(
                    text("SET LOCAL app.current_org_id = :org_id"),
                    {"org_id": str(org_id)},
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def run_async(coro):
    """Run an async coroutine in a new event loop for Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class BaseTask(Task):
    """Base task with structured logging and standardized error handling."""

    abstract = True
    autoretry_for = (ConnectionError, TimeoutError, OSError)
    retry_backoff = True
    retry_backoff_max = 300
    max_retries = 3
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task_failed",
            task=self.name,
            task_id=task_id,
            error=str(exc),
        )
        # Update meeting status to "failed" if meeting_id is the first arg
        if args:
            meeting_id = args[0]
            try:
                async def _update_status():
                    async with get_task_session() as session:
                        from app.models.meeting import Meeting
                        from sqlalchemy import select
                        result = await session.execute(
                            select(Meeting).where(Meeting.id == meeting_id)
                        )
                        meeting = result.scalar_one_or_none()
                        if meeting and meeting.status not in ("analyzed", "failed"):
                            meeting.status = "failed"

                run_async(_update_status())
            except Exception:
                logger.warning("failed_to_update_meeting_status", meeting_id=meeting_id)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "task_succeeded",
            task=self.name,
            task_id=task_id,
        )
