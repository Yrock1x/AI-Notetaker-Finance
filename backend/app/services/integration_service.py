import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode
from uuid import UUID

import httpx
import structlog
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    DomainValidationError,
    ExternalServiceError,
    NotFoundError,
)
from app.models.integration_credential import IntegrationCredential

logger = structlog.get_logger(__name__)

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

# Token expiry buffer — refresh tokens 5 minutes before they expire
_TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)


class IntegrationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------
    # OAuth flow — public
    # ------------------------------------------------------------------

    async def initiate_oauth(
        self,
        user_id: UUID,
        org_id: UUID,
        platform: str,
        redirect_uri: str,
    ) -> str:
        """Initiate an OAuth flow and return the authorization URL.

        The *state* parameter encodes the user_id, org_id, and a random nonce
        so the callback can restore context without requiring an active session.
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise DomainValidationError(f"Unsupported platform: {platform}")

        config = OAUTH_CONFIGS[platform]

        # Encode user context into the state token so the callback can
        # recover user_id and org_id (the redirect comes from the provider,
        # so there is no Bearer token on the request).
        state_payload = json.dumps(
            {
                "user_id": str(user_id),
                "org_id": str(org_id),
                "nonce": secrets.token_urlsafe(16),
            }
        )
        state = base64.urlsafe_b64encode(state_payload.encode()).decode()

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
        redirect_uri: str,
    ) -> IntegrationCredential:
        """Handle the OAuth callback — exchange code for tokens and persist."""
        if platform not in SUPPORTED_PLATFORMS:
            raise DomainValidationError(f"Unsupported platform: {platform}")

        # Exchange the authorization code for real tokens
        token_data = await self._exchange_code_for_tokens(
            platform=platform,
            code=code,
            redirect_uri=redirect_uri,
        )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        scopes = token_data.get("scope", OAUTH_CONFIGS[platform]["scopes"])

        now = datetime.now(timezone.utc)
        token_expires_at = (
            now + timedelta(seconds=int(expires_in)) if expires_in else None
        )

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

        if existing:
            existing.access_token_encrypted = self._encrypt_token(access_token)
            existing.refresh_token_encrypted = (
                self._encrypt_token(refresh_token) if refresh_token else None
            )
            existing.token_expires_at = token_expires_at
            existing.scopes = scopes
            existing.is_active = True
            await self.db.flush()
            logger.info(
                "integration_credential_updated",
                platform=platform,
                user_id=str(user_id),
            )
            return existing

        credential = IntegrationCredential(
            org_id=org_id,
            user_id=user_id,
            platform=platform,
            access_token_encrypted=self._encrypt_token(access_token),
            refresh_token_encrypted=(
                self._encrypt_token(refresh_token) if refresh_token else None
            ),
            token_expires_at=token_expires_at,
            scopes=scopes,
            is_active=True,
        )
        self.db.add(credential)
        await self.db.flush()
        logger.info(
            "integration_credential_created",
            platform=platform,
            user_id=str(user_id),
        )
        return credential

    async def refresh_access_token(
        self, credential: IntegrationCredential
    ) -> Optional[IntegrationCredential]:
        """Refresh an expired access token using the stored refresh token.

        Returns the updated credential, or ``None`` for platforms whose tokens
        do not expire (e.g. Slack bot tokens).
        """
        platform = credential.platform

        # Slack bot tokens do not expire — nothing to refresh.
        if platform == "slack":
            logger.debug("slack_token_refresh_noop")
            return None

        if not credential.refresh_token_encrypted:
            raise DomainValidationError(
                f"No refresh token stored for {platform} credential"
            )

        refresh_tok = self._decrypt_token(credential.refresh_token_encrypted)

        config = OAUTH_CONFIGS[platform]
        token_url = config["token_url"]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if platform == "zoom":
                    # Zoom uses Basic auth (base64 of client_id:client_secret)
                    basic = self._zoom_basic_auth()
                    resp = await client.post(
                        token_url,
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_tok,
                        },
                        headers={"Authorization": f"Basic {basic}"},
                    )
                else:
                    # Teams / Outlook use form-encoded client credentials
                    resp = await client.post(
                        token_url,
                        data={
                            "grant_type": "refresh_token",
                            "client_id": self._get_client_id(platform),
                            "client_secret": self._get_client_secret(platform),
                            "refresh_token": refresh_tok,
                        },
                    )

                resp.raise_for_status()
                token_data = resp.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "token_refresh_failed",
                platform=platform,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise ExternalServiceError(
                platform, f"Token refresh failed ({exc.response.status_code})"
            )
        except httpx.HTTPError as exc:
            logger.error("token_refresh_network_error", platform=platform, error=str(exc))
            raise ExternalServiceError(platform, f"Token refresh network error: {exc}")

        now = datetime.now(timezone.utc)
        credential.access_token_encrypted = self._encrypt_token(
            token_data["access_token"]
        )
        if token_data.get("refresh_token"):
            credential.refresh_token_encrypted = self._encrypt_token(
                token_data["refresh_token"]
            )
        if token_data.get("expires_in"):
            credential.token_expires_at = now + timedelta(
                seconds=int(token_data["expires_in"])
            )
        await self.db.flush()

        logger.info("token_refreshed", platform=platform)
        return credential

    async def get_valid_access_token(
        self, user_id: UUID, org_id: UUID, platform: str
    ) -> str:
        """Return a valid (non-expired) decrypted access token.

        Transparently refreshes the token if it is about to expire within
        the next 5 minutes.
        """
        credential = await self.get_credentials(user_id, org_id, platform)
        if credential is None:
            raise NotFoundError("IntegrationCredential", platform)

        # Check if token is expired or about to expire
        if credential.token_expires_at is not None:
            now = datetime.now(timezone.utc)
            if credential.token_expires_at < now + _TOKEN_EXPIRY_BUFFER:
                logger.info(
                    "token_expired_refreshing",
                    platform=platform,
                    expires_at=credential.token_expires_at.isoformat(),
                )
                refreshed = await self.refresh_access_token(credential)
                if refreshed is not None:
                    credential = refreshed

        return self._decrypt_token(credential.access_token_encrypted)

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # State token helpers
    # ------------------------------------------------------------------

    @staticmethod
    def encode_state(user_id: UUID, org_id: UUID) -> str:
        """Encode user_id and org_id into a base64 state token."""
        payload = json.dumps(
            {
                "user_id": str(user_id),
                "org_id": str(org_id),
                "nonce": secrets.token_urlsafe(16),
            }
        )
        return base64.urlsafe_b64encode(payload.encode()).decode()

    @staticmethod
    def decode_state(state: str) -> dict:
        """Decode a base64 state token back to {user_id, org_id, nonce}.

        Raises DomainValidationError if the token cannot be decoded.
        """
        try:
            raw = base64.urlsafe_b64decode(state.encode())
            data = json.loads(raw)
            return {
                "user_id": UUID(data["user_id"]),
                "org_id": UUID(data["org_id"]),
            }
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise DomainValidationError(f"Invalid OAuth state token: {exc}")

    # ------------------------------------------------------------------
    # Private — token exchange
    # ------------------------------------------------------------------

    async def _exchange_code_for_tokens(
        self,
        platform: str,
        code: str,
        redirect_uri: str,
    ) -> dict:
        """Exchange an authorization code for access/refresh tokens.

        Returns a dict with at least ``access_token``; may also include
        ``refresh_token``, ``expires_in``, ``scope``, and ``token_type``.
        """
        config = OAUTH_CONFIGS[platform]
        token_url = config["token_url"]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if platform == "zoom":
                    basic = self._zoom_basic_auth()
                    resp = await client.post(
                        token_url,
                        data={
                            "grant_type": "authorization_code",
                            "code": code,
                            "redirect_uri": redirect_uri,
                        },
                        headers={"Authorization": f"Basic {basic}"},
                    )
                elif platform in ("teams", "outlook"):
                    resp = await client.post(
                        token_url,
                        data={
                            "grant_type": "authorization_code",
                            "client_id": self._get_client_id(platform),
                            "client_secret": self._get_client_secret(platform),
                            "code": code,
                            "redirect_uri": redirect_uri,
                            "scope": config["scopes"],
                        },
                    )
                elif platform == "slack":
                    resp = await client.post(
                        token_url,
                        data={
                            "client_id": self._get_client_id(platform),
                            "client_secret": self._get_client_secret(platform),
                            "code": code,
                            "redirect_uri": redirect_uri,
                        },
                    )
                else:
                    raise DomainValidationError(
                        f"Token exchange not implemented for {platform}"
                    )

                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "token_exchange_failed",
                platform=platform,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise ExternalServiceError(
                platform,
                f"Token exchange failed ({exc.response.status_code})",
            )
        except httpx.HTTPError as exc:
            logger.error(
                "token_exchange_network_error",
                platform=platform,
                error=str(exc),
            )
            raise ExternalServiceError(
                platform, f"Token exchange network error: {exc}"
            )

        # Slack nests its tokens inside an `authed_user` or top-level object
        if platform == "slack":
            # Slack V2 OAuth returns access_token at top level for bot tokens
            if "ok" in data and not data.get("ok"):
                raise ExternalServiceError(
                    "Slack", data.get("error", "Unknown Slack OAuth error")
                )
            return {
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
                "scope": data.get("scope", ""),
                "token_type": data.get("token_type", "bearer"),
            }

        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope", ""),
            "token_type": data.get("token_type", "bearer"),
        }

    # ------------------------------------------------------------------
    # Private — credentials & crypto
    # ------------------------------------------------------------------

    def _get_client_id(self, platform: str) -> str:
        """Get the OAuth client ID for a platform from settings."""
        return getattr(self.settings, f"{platform}_client_id", "")

    def _get_client_secret(self, platform: str) -> str:
        """Get the OAuth client secret for a platform from settings."""
        return getattr(self.settings, f"{platform}_client_secret", "")

    def _zoom_basic_auth(self) -> str:
        """Return the Base64-encoded ``client_id:client_secret`` for Zoom."""
        raw = f"{self._get_client_id('zoom')}:{self._get_client_secret('zoom')}"
        return base64.b64encode(raw.encode()).decode()

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
