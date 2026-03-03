"""Unit tests for the IntegrationService.

Tests cover OAuth flow initiation, callback handling, credential management,
and token encryption/decryption. All database and HTTP interactions are mocked.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.exceptions import DomainValidationError, NotFoundError
from app.models.integration_credential import IntegrationCredential
from app.services.integration_service import IntegrationService


@pytest.fixture
def encryption_key() -> str:
    """Generate a valid Fernet encryption key for tests."""
    return Fernet.generate_key().decode()


@pytest.fixture
def test_settings(encryption_key: str) -> Settings:
    """Create test settings with valid encryption key and OAuth credentials."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        token_encryption_key=encryption_key,
        zoom_client_id="test-zoom-client-id",
        teams_client_id="test-teams-client-id",
        slack_client_id="test-slack-client-id",
        outlook_client_id="test-outlook-client-id",
    )


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def service(mock_db: AsyncMock, test_settings: Settings) -> IntegrationService:
    """Create an IntegrationService with mocked dependencies."""
    return IntegrationService(db=mock_db, settings=test_settings)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


class TestInitiateOAuth:
    """Tests for IntegrationService.initiate_oauth."""

    async def test_initiate_oauth_generates_authorization_url_zoom(
        self, service: IntegrationService, user_id: uuid.UUID, org_id: uuid.UUID
    ):
        """Initiating OAuth for Zoom should return an authorization URL
        containing the Zoom authorize endpoint."""
        url = await service.initiate_oauth(
            user_id=user_id,
            org_id=org_id,
            platform="zoom",
            redirect_uri="http://localhost/callback",
        )
        assert "https://zoom.us/oauth/authorize" in url
        assert "response_type=code" in url
        assert "client_id=test-zoom-client-id" in url
        assert "redirect_uri=" in url
        assert "scope=" in url
        assert "state=" in url

    async def test_initiate_oauth_generates_authorization_url_teams(
        self, service: IntegrationService, user_id: uuid.UUID, org_id: uuid.UUID
    ):
        """Initiating OAuth for Teams should return a Microsoft authorization URL."""
        url = await service.initiate_oauth(
            user_id=user_id,
            org_id=org_id,
            platform="teams",
            redirect_uri="http://localhost/callback",
        )
        assert "login.microsoftonline.com" in url
        assert "response_type=code" in url
        assert "client_id=test-teams-client-id" in url

    async def test_initiate_oauth_generates_authorization_url_slack(
        self, service: IntegrationService, user_id: uuid.UUID, org_id: uuid.UUID
    ):
        """Initiating OAuth for Slack should return a Slack authorization URL."""
        url = await service.initiate_oauth(
            user_id=user_id,
            org_id=org_id,
            platform="slack",
            redirect_uri="http://localhost/callback",
        )
        assert "https://slack.com/oauth/v2/authorize" in url
        assert "client_id=test-slack-client-id" in url

    async def test_initiate_oauth_generates_authorization_url_outlook(
        self, service: IntegrationService, user_id: uuid.UUID, org_id: uuid.UUID
    ):
        """Initiating OAuth for Outlook should return a Microsoft authorization URL."""
        url = await service.initiate_oauth(
            user_id=user_id,
            org_id=org_id,
            platform="outlook",
            redirect_uri="http://localhost/callback",
        )
        assert "login.microsoftonline.com" in url
        assert "client_id=test-outlook-client-id" in url

    async def test_initiate_oauth_unsupported_platform_raises(
        self, service: IntegrationService, user_id: uuid.UUID, org_id: uuid.UUID
    ):
        """Initiating OAuth for an unsupported platform should raise DomainValidationError."""
        with pytest.raises(DomainValidationError, match="Unsupported platform"):
            await service.initiate_oauth(
                user_id=user_id,
                org_id=org_id,
                platform="webex",
                redirect_uri="http://localhost/callback",
            )


class TestHandleOAuthCallback:
    """Tests for IntegrationService.handle_oauth_callback."""

    @patch.object(IntegrationService, "_exchange_code_for_tokens")
    async def test_handle_oauth_callback_creates_credential(
        self,
        mock_exchange,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """OAuth callback with no existing credential should create a new
        IntegrationCredential."""
        mock_exchange.return_value = {
            "access_token": "real-access-token",
            "refresh_token": "real-refresh-token",
            "expires_in": 3600,
            "scope": "meeting:read recording:read user:read",
        }

        # Simulate no existing credential
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        credential = await service.handle_oauth_callback(
            user_id=user_id,
            org_id=org_id,
            platform="zoom",
            code="test-auth-code",
            state="test-state",
            redirect_uri="http://localhost/callback",
        )

        assert credential.platform == "zoom"
        assert credential.org_id == org_id
        assert credential.user_id == user_id
        assert credential.is_active is True
        assert credential.scopes == "meeting:read recording:read user:read"
        assert credential.access_token_encrypted is not None
        assert credential.token_expires_at is not None
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited()

    @patch.object(IntegrationService, "_exchange_code_for_tokens")
    async def test_handle_oauth_callback_updates_existing_credential(
        self,
        mock_exchange,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """OAuth callback with an existing credential should update it
        instead of creating a new one."""
        mock_exchange.return_value = {
            "access_token": "new-real-access-token",
            "refresh_token": "new-real-refresh-token",
            "expires_in": 3600,
            "scope": "meeting:read recording:read user:read",
        }

        existing = IntegrationCredential(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            platform="zoom",
            access_token_encrypted="old-encrypted-token",  # noqa: S106
            token_expires_at=datetime.now(UTC) - timedelta(hours=1),
            scopes="old:scopes",
            is_active=False,
        )
        existing.created_at = datetime.now(UTC)
        existing.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result

        credential = await service.handle_oauth_callback(
            user_id=user_id,
            org_id=org_id,
            platform="zoom",
            code="new-auth-code",
            state="test-state",
            redirect_uri="http://localhost/callback",
        )

        assert credential is existing
        assert credential.is_active is True
        assert credential.access_token_encrypted != "old-encrypted-token"  # noqa: S105
        assert credential.scopes == "meeting:read recording:read user:read"
        # Should NOT add a new object since we are updating
        mock_db.add.assert_not_called()
        mock_db.flush.assert_awaited()


class TestDisconnect:
    """Tests for IntegrationService.disconnect."""

    async def test_disconnect_deactivates_credential(
        self,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """Disconnecting an integration should set is_active to False."""
        existing = IntegrationCredential(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            platform="slack",
            access_token_encrypted="encrypted-token",  # noqa: S106
            is_active=True,
        )
        existing.created_at = datetime.now(UTC)
        existing.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result

        await service.disconnect(user_id=user_id, org_id=org_id, platform="slack")

        assert existing.is_active is False
        mock_db.flush.assert_awaited()

    async def test_disconnect_not_found_raises(
        self,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """Disconnecting a non-existent integration should raise NotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="not found"):
            await service.disconnect(user_id=user_id, org_id=org_id, platform="slack")


class TestGetCredentials:
    """Tests for IntegrationService.get_credentials."""

    async def test_get_credentials_returns_active_only(
        self,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """get_credentials should return only active credentials
        (the query filters by is_active)."""
        active_cred = IntegrationCredential(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            platform="zoom",
            access_token_encrypted="enc-token",  # noqa: S106
            is_active=True,
        )
        active_cred.created_at = datetime.now(UTC)
        active_cred.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = active_cred
        mock_db.execute.return_value = mock_result

        result = await service.get_credentials(
            user_id=user_id, org_id=org_id, platform="zoom"
        )

        assert result is active_cred
        assert result.is_active is True


class TestListIntegrations:
    """Tests for IntegrationService.list_integrations."""

    async def test_list_integrations_returns_user_org_scoped(
        self,
        service: IntegrationService,
        mock_db: AsyncMock,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ):
        """list_integrations should return all active credentials for a user within their org."""
        creds = [
            IntegrationCredential(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                platform="zoom",
                access_token_encrypted="enc-1",  # noqa: S106
                is_active=True,
            ),
            IntegrationCredential(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                platform="slack",
                access_token_encrypted="enc-2",  # noqa: S106
                is_active=True,
            ),
        ]
        for c in creds:
            c.created_at = datetime.now(UTC)
            c.updated_at = datetime.now(UTC)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = creds
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.list_integrations(user_id=user_id, org_id=org_id)

        assert len(result) == 2
        assert result[0].platform == "zoom"
        assert result[1].platform == "slack"


class TestTokenEncryption:
    """Tests for encrypt/decrypt token round-trip and error handling."""

    def test_encrypt_decrypt_token_roundtrip(
        self, service: IntegrationService
    ):
        """Encrypting and then decrypting a token should return the original value."""
        original = "my-secret-access-token"
        encrypted = service._encrypt_token(original)

        assert encrypted != original
        decrypted = service._decrypt_token(encrypted)
        assert decrypted == original

    def test_decrypt_with_wrong_key_raises(
        self, mock_db: AsyncMock
    ):
        """Decrypting a token with the wrong encryption key should raise ValueError."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        settings1 = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            app_env="development",
            token_encryption_key=key1,
        )
        settings2 = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            app_env="development",
            token_encryption_key=key2,
        )

        service1 = IntegrationService(db=mock_db, settings=settings1)
        service2 = IntegrationService(db=mock_db, settings=settings2)

        encrypted = service1._encrypt_token("my-token")
        with pytest.raises(ValueError, match="Failed to decrypt"):
            service2._decrypt_token(encrypted)
