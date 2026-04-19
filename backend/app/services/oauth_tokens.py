"""Shared OAuth primitives: Fernet token encryption, signed state tokens, and
credential storage against ``integration_credentials`` in Supabase.

Platform-specific authorize-URL / code-exchange / refresh logic lives under
``app.integrations.<platform>.oauth``. This module is the common layer each
of those helpers calls into.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import structlog
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from supabase import Client

from app.core.config import settings

logger = structlog.get_logger(__name__)


Platform = Literal["zoom", "microsoft", "google", "slack"]


# ---------------------------------------------------------------------------
# Token encryption (Fernet)
# ---------------------------------------------------------------------------


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not configured — cannot encrypt OAuth tokens"
        )
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt OAuth token") from exc


# ---------------------------------------------------------------------------
# State token — signed JWT that survives the OAuth redirect round-trip.
# Carries org_id/user_id/platform plus a nonce so the callback can look the
# user up without trusting anything in the query string.
# ---------------------------------------------------------------------------


_STATE_TTL_SECONDS = 600  # 10 min


def _state_secret() -> str:
    secret = settings.worker_internal_token or settings.token_encryption_key
    if not secret:
        raise RuntimeError(
            "No secret available to sign OAuth state — set WORKER_INTERNAL_TOKEN"
        )
    return secret


def build_state(org_id: UUID, user_id: UUID, platform: Platform) -> str:
    now = int(time.time())
    payload = {
        "org_id": str(org_id),
        "user_id": str(user_id),
        "platform": platform,
        "nonce": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + _STATE_TTL_SECONDS,
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def verify_state(state: str) -> dict:
    try:
        claims = jwt.decode(state, _state_secret(), algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(f"invalid OAuth state: {exc}") from exc
    # jose verifies exp; nothing else to do.
    return claims


# ---------------------------------------------------------------------------
# Credential storage (integration_credentials)
# ---------------------------------------------------------------------------


def redirect_uri_for(platform: Platform) -> str:
    """Canonical OAuth redirect URI for a platform.

    Points at the worker because only the worker holds the client secret.
    The worker finishes the token exchange, then 302s the browser back to
    ``settings.frontend_url``.
    """
    api_base = (settings.public_api_url or "http://localhost:8000").rstrip("/")
    return f"{api_base}/api/v1/integrations/{platform}/callback"


def save_credentials(
    sb: Client,
    *,
    org_id: UUID,
    user_id: UUID,
    platform: Platform,
    access_token: str,
    refresh_token: str | None,
    expires_in_seconds: int | None,
    scopes: str | None,
) -> None:
    """Upsert an ``integration_credentials`` row. Expects the service-role
    client — the row is keyed on (org_id, user_id, platform)."""
    expires_at = (
        (datetime.now(UTC) + timedelta(seconds=int(expires_in_seconds))).isoformat()
        if expires_in_seconds
        else None
    )
    row = {
        "org_id": str(org_id),
        "user_id": str(user_id),
        "platform": platform,
        "access_token_encrypted": encrypt_token(access_token),
        "refresh_token_encrypted": (
            encrypt_token(refresh_token) if refresh_token else None
        ),
        "token_expires_at": expires_at,
        "scopes": scopes,
        "is_active": True,
    }
    sb.table("integration_credentials").upsert(
        row, on_conflict="org_id,user_id,platform"
    ).execute()
    logger.info(
        "oauth_credentials_saved", platform=platform, user_id=str(user_id)
    )


def deactivate_credentials(
    sb: Client, *, org_id: UUID, user_id: UUID, platform: Platform
) -> None:
    sb.table("integration_credentials").update({"is_active": False}).eq(
        "org_id", str(org_id)
    ).eq("user_id", str(user_id)).eq("platform", platform).execute()


def list_user_integrations(sb: Client, *, user_id: UUID) -> list[dict]:
    """Return a JSON-serialisable list of the user's active integrations."""
    resp = (
        sb.table("integration_credentials")
        .select("platform,is_active,scopes,created_at,token_expires_at")
        .eq("user_id", str(user_id))
        .eq("is_active", True)
        .execute()
    )
    return [
        {
            "platform": r["platform"],
            "is_active": r["is_active"],
            "scopes": r.get("scopes"),
            "connected_at": r["created_at"],
            "token_expires_at": r.get("token_expires_at"),
        }
        for r in (resp.data or [])
    ]


async def get_valid_access_token(
    sb: Client, *, org_id: UUID, user_id: UUID, platform: Platform
) -> str:
    """Fetch the user's access token, refreshing via the platform helper if
    the current one is within 60s of expiry."""
    resp = (
        sb.table("integration_credentials")
        .select("*")
        .eq("org_id", str(org_id))
        .eq("user_id", str(user_id))
        .eq("platform", platform)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise RuntimeError(f"No active {platform} credentials for user {user_id}")
    row = rows[0]

    access = decrypt_token(row["access_token_encrypted"])
    expires_at_iso = row.get("token_expires_at")
    needs_refresh = False
    if expires_at_iso:
        expires_at = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        needs_refresh = expires_at <= datetime.now(UTC) + timedelta(seconds=60)

    if not needs_refresh:
        return access

    if not row.get("refresh_token_encrypted"):
        raise RuntimeError(
            f"{platform} access token is expired and no refresh token is stored"
        )
    refresh = decrypt_token(row["refresh_token_encrypted"])

    # Dispatch to the platform helper.
    from app.integrations.google.oauth import refresh_google
    from app.integrations.microsoft.oauth import refresh_microsoft
    from app.integrations.zoom.oauth import refresh_zoom

    if platform == "zoom":
        new_tokens = await refresh_zoom(refresh)
    elif platform == "microsoft":
        new_tokens = await refresh_microsoft(refresh)
    elif platform == "google":
        new_tokens = await refresh_google(refresh)
    else:
        raise RuntimeError(f"No refresh flow implemented for platform={platform}")

    save_credentials(
        sb,
        org_id=org_id,
        user_id=user_id,
        platform=platform,
        access_token=new_tokens["access_token"],
        # Some providers (Google) don't return a new refresh token on every
        # call — fall back to the existing one so we never wipe it.
        refresh_token=new_tokens.get("refresh_token") or refresh,
        expires_in_seconds=new_tokens.get("expires_in"),
        scopes=new_tokens.get("scope") or row.get("scopes"),
    )
    return new_tokens["access_token"]
