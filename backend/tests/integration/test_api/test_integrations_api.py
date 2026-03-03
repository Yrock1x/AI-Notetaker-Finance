"""Integration tests for the /api/v1/integrations API endpoints.

These tests exercise the HTTP layer (routing, serialization, dependency
injection) using the FastAPI test client. Database and auth dependencies
are overridden with mocks.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.dependencies import get_current_user, get_db, get_db_with_rls, get_org_id
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user for API tests."""
    user = User(
        id=uuid.uuid4(),
        cognito_sub=f"cognito-{uuid.uuid4()}",
        email="api-tester@example.com",
        full_name="API Tester",
        is_active=True,
    )
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def demo_settings() -> Settings:
    """Settings with demo_mode enabled."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        demo_mode=True,
        demo_jwt_secret="test-secret-not-default-value",
    )


@pytest.fixture
def api_app(mock_user: User, org_id: uuid.UUID, demo_settings: Settings) -> FastAPI:
    """FastAPI app with mocked auth, db, and org dependencies."""
    from app.main import create_app

    app = create_app()
    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    async def override_get_db_with_rls():
        yield mock_db

    async def override_get_current_user():
        return mock_user

    async def override_get_org_id():
        return org_id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_with_rls] = override_get_db_with_rls
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_org_id] = override_get_org_id

    return app


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncClient:
    """AsyncClient for API tests."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# List Integrations
# ===========================================================================


class TestListIntegrations:
    """Tests for GET /api/v1/integrations."""

    @patch("app.api.v1.integrations.get_settings")
    async def test_list_integrations_demo_mode(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        demo_settings: Settings,
    ):
        """In demo mode, listing integrations should return all 4 platforms with their status."""
        mock_get_settings.return_value = demo_settings

        resp = await api_client.get("/api/v1/integrations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        platforms = {item["platform"] for item in data}
        assert platforms == {"zoom", "teams", "slack", "outlook"}
        # All should be inactive by default in demo mode
        for item in data:
            assert "is_active" in item
            assert "platform" in item


# ===========================================================================
# Connect Platform
# ===========================================================================


class TestConnectPlatform:
    """Tests for POST /api/v1/integrations/{platform}/connect."""

    @patch("app.api.v1.integrations.get_settings")
    async def test_connect_platform_demo_mode(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        demo_settings: Settings,
    ):
        """In demo mode, connecting a platform should instantly mark it as connected."""
        mock_get_settings.return_value = demo_settings

        resp = await api_client.post("/api/v1/integrations/zoom/connect")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["platform"] == "zoom"


# ===========================================================================
# Disconnect Platform
# ===========================================================================


class TestDisconnectPlatform:
    """Tests for DELETE /api/v1/integrations/{platform}/disconnect."""

    @patch("app.api.v1.integrations.get_settings")
    async def test_disconnect_platform_demo_mode(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        demo_settings: Settings,
    ):
        """In demo mode, disconnecting a platform should return 204."""
        mock_get_settings.return_value = demo_settings

        # Connect first
        await api_client.post("/api/v1/integrations/slack/connect")

        resp = await api_client.delete("/api/v1/integrations/slack/disconnect")

        assert resp.status_code == 204


# ===========================================================================
# Bot Sessions
# ===========================================================================


class TestBotSessionsApi:
    """Tests for the /api/v1/integrations/bot/sessions endpoints."""

    @patch("app.api.v1.integrations.get_settings")
    async def test_schedule_bot_session(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        api_app: FastAPI,
        demo_settings: Settings,
    ):
        """POST /bot/sessions should create a new bot session."""
        mock_get_settings.return_value = demo_settings

        # We need to mock the BotService to avoid real DB calls
        from app.services.bot_service import BotService
        from app.models.meeting_bot_session import MeetingBotSession

        deal_id = uuid.uuid4()
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_session = MeetingBotSession(
            id=session_id,
            org_id=uuid.uuid4(),
            deal_id=deal_id,
            platform="zoom",
            meeting_url="https://zoom.us/j/test123",
            status="scheduled",
            consent_obtained=False,
            created_by=uuid.uuid4(),
        )
        mock_session.created_at = now
        mock_session.updated_at = now
        mock_session.scheduled_start = now
        mock_session.actual_start = None
        mock_session.actual_end = None

        with patch.object(
            BotService, "schedule_bot", new_callable=AsyncMock, return_value=mock_session
        ):
            resp = await api_client.post(
                "/api/v1/integrations/bot/sessions",
                json={
                    "meeting_url": "https://zoom.us/j/test123",
                    "platform": "zoom",
                    "deal_id": str(deal_id),
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["platform"] == "zoom"
        assert data["status"] == "scheduled"
        assert data["meeting_url"] == "https://zoom.us/j/test123"

    @patch("app.api.v1.integrations.get_settings")
    async def test_list_bot_sessions(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        demo_settings: Settings,
    ):
        """GET /bot/sessions should return a list of bot sessions."""
        mock_get_settings.return_value = demo_settings

        from app.services.bot_service import BotService
        from app.models.meeting_bot_session import MeetingBotSession

        now = datetime.now(timezone.utc)
        sessions = []
        for i in range(2):
            s = MeetingBotSession(
                id=uuid.uuid4(),
                org_id=uuid.uuid4(),
                deal_id=uuid.uuid4(),
                platform="zoom",
                meeting_url=f"https://zoom.us/j/{i}",
                status="scheduled",
                consent_obtained=False,
                created_by=uuid.uuid4(),
            )
            s.created_at = now
            s.updated_at = now
            s.scheduled_start = None
            s.actual_start = None
            s.actual_end = None
            sessions.append(s)

        with patch.object(
            BotService,
            "list_sessions",
            new_callable=AsyncMock,
            return_value={"items": sessions, "cursor": None, "has_more": False},
        ):
            resp = await api_client.get("/api/v1/integrations/bot/sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @patch("app.api.v1.integrations.get_settings")
    async def test_cancel_bot_session(
        self,
        mock_get_settings: MagicMock,
        api_client: AsyncClient,
        demo_settings: Settings,
    ):
        """DELETE /bot/sessions/{session_id} should cancel a bot session."""
        mock_get_settings.return_value = demo_settings

        from app.services.bot_service import BotService

        session_id = uuid.uuid4()

        with patch.object(
            BotService, "cancel_bot", new_callable=AsyncMock, return_value=None
        ):
            resp = await api_client.delete(
                f"/api/v1/integrations/bot/sessions/{session_id}"
            )

        assert resp.status_code == 204
