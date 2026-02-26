import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.base import Base
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://dealwise:localdev@localhost:5432/dealwise_test"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(database_url=TEST_DATABASE_URL, app_env="development")


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    """Transactional test session that rolls back after each test."""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = User(
        id=uuid.uuid4(),
        cognito_sub=f"cognito-{uuid.uuid4()}",
        email="testuser@example.com",
        full_name="Test User",
        is_active=True,
    )
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def app(db_session: AsyncSession, mock_user: User) -> FastAPI:
    """FastAPI test app with mocked dependencies."""
    app = create_app()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
