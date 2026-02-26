from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from app.core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.app_env == "development",
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_with_rls_context(org_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session with Row-Level Security context set.

    Sets the PostgreSQL session variable `app.current_org_id` so that
    RLS policies can filter rows by organization.
    """
    async with async_session_factory() as session:
        try:
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
