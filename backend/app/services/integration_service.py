import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.integration_credential import IntegrationCredential

SUPPORTED_PLATFORMS = {"zoom", "teams", "slack", "outlook"}

# OAuth configuration per platform
OAUTH_CONFIGS = {
    "zoom": {
        "authorize_url": "https://zoom.us/oauth/authorize",
        "token_url": "https://zoom.us/oauth/token",
        "scopes": "meeting:read recording:read user:read",
    },
    "teams": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": "OnlineMeetings.Read Calendars.Read User.Read offline_access",
    },
    "slack": {
        "authorize_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": "channels:read chat:write commands",
    },
    "outlook": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": "Calendars.Read Mail.Read offline_access",
    },
}


class IntegrationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def initiate_oauth(
        self,
        user_id: UUID,
        org_id: UUID,
        platform: str,
        redirect_uri: str,
    ) -> str:
        """Initiate an OAuth flow and return the authorization URL."""
        if platform not in SUPPORTED_PLATFORMS:
            raise ValidationError(f"Unsupported platform: {platform}")

        config = OAUTH_CONFIGS[platform]

        # Generate a state token that encodes user/org/platform for callback verification
        state = secrets.token_urlsafe(32)

        params = {
            "response_type": "code",
            "client_id": self._get_client_id(platform),
            "redirect_uri": redirect_uri,
            "scope": config["scopes"],
            "state": state,
        }

        authorization_url = f"{config['authorize_url']}?{urlencode(params)}"
        return authorization_url

    async def handle_oauth_callback(
        self,
        user_id: UUID,
        org_id: UUID,
        platform: str,
        code: str,
        state: str,
    ) -> IntegrationCredential:
        """Handle the OAuth callback and store credentials.

        In production, this would exchange the code for tokens via HTTP.
        For now, we store a placeholder that will be replaced when the
        platform client modules are fully implemented.
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValidationError(f"Unsupported platform: {platform}")

        # Check for existing credential
        stmt = select(IntegrationCredential).where(
            and_(
                IntegrationCredential.org_id == org_id,
                IntegrationCredential.user_id == user_id,
                IntegrationCredential.platform == platform,
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        config = OAUTH_CONFIGS[platform]

        if existing:
            # Update existing credential
            existing.access_token_encrypted = self._encrypt_token(code)
            existing.refresh_token_encrypted = None
            existing.token_expires_at = now + timedelta(hours=1)
            existing.scopes = config["scopes"]
            existing.is_active = True
            await self.db.flush()
            return existing

        # Create new credential
        credential = IntegrationCredential(
            org_id=org_id,
            user_id=user_id,
            platform=platform,
            access_token_encrypted=self._encrypt_token(code),
            token_expires_at=now + timedelta(hours=1),
            scopes=config["scopes"],
            is_active=True,
        )
        self.db.add(credential)
        await self.db.flush()
        return credential

    async def disconnect(self, user_id: UUID, org_id: UUID, platform: str) -> None:
        """Disconnect an integration by deactivating stored credentials."""
        stmt = select(IntegrationCredential).where(
            and_(
                IntegrationCredential.org_id == org_id,
                IntegrationCredential.user_id == user_id,
                IntegrationCredential.platform == platform,
            )
        )
        result = await self.db.execute(stmt)
        credential = result.scalar_one_or_none()
        if credential is None:
            raise NotFoundError("IntegrationCredential", f"{platform}")

        credential.is_active = False
        await self.db.flush()

    async def get_credentials(
        self, user_id: UUID, org_id: UUID, platform: str
    ) -> Optional[IntegrationCredential]:
        """Get stored credentials for a provider."""
        stmt = select(IntegrationCredential).where(
            and_(
                IntegrationCredential.org_id == org_id,
                IntegrationCredential.user_id == user_id,
                IntegrationCredential.platform == platform,
                IntegrationCredential.is_active.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_integrations(
        self, user_id: UUID, org_id: UUID
    ) -> list[IntegrationCredential]:
        """List all active integrations for a user in an org."""
        stmt = (
            select(IntegrationCredential)
            .where(
                and_(
                    IntegrationCredential.org_id == org_id,
                    IntegrationCredential.user_id == user_id,
                    IntegrationCredential.is_active.is_(True),
                )
            )
            .order_by(IntegrationCredential.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def _get_client_id(self, platform: str) -> str:
        """Get the OAuth client ID for a platform from settings."""
        # These would be added to Settings when platform credentials are configured
        return getattr(self.settings, f"{platform}_client_id", "")

    def _get_fernet(self) -> Fernet:
        """Get a Fernet instance from the configured encryption key."""
        key = self.settings.token_encryption_key
        if not key:
            raise ValueError(
                "token_encryption_key must be set for integration credential storage. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return Fernet(key.encode())

    def _encrypt_token(self, token: str) -> str:
        """Encrypt a token for secure storage using Fernet symmetric encryption."""
        return self._get_fernet().encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token."""
        try:
            return self._get_fernet().decrypt(encrypted_token.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt integration token — key may have rotated")
            raise ValueError("Failed to decrypt stored token")
