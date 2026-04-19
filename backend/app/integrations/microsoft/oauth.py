"""Microsoft identity OAuth 2.0 — covers Teams, Outlook Calendar, and Meet
metadata via Microsoft Graph.

Uses the ``common`` tenant so both work and personal Microsoft accounts can
authenticate. For tenant-locked deployments switch ``common`` to the tenant
GUID.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger(__name__)

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105 - public OAuth endpoint

# Delegated scopes for Microsoft 365 work/school accounts (Entra ID). The
# advanced scopes — OnlineMeetings.Read, Chat.Read, CallRecords.Read.All —
# only exist in the work/school universe; users on personal Microsoft
# accounts (outlook.com etc.) will fail here with invalid_scope. That's
# the right tradeoff for a B2B product whose target customers are all on
# corporate tenants. CallRecords.Read.All additionally requires a tenant
# admin to "Grant admin consent" once per firm in the Azure app config.
SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "email",
    "User.Read",
    "Calendars.Read",
    "OnlineMeetings.Read",
    "Chat.Read",
    "CallRecords.Read.All",
]


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    *, client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": " ".join(SCOPES),
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "microsoft_code_exchange_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope"),
            "token_type": data.get("token_type", "Bearer"),
            "id_token": data.get("id_token"),
        }


async def refresh_microsoft(refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token. Reads client creds
    from settings so callers don't need to plumb them through."""
    from app.core.config import settings

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(SCOPES),
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "microsoft_refresh_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope"),
        }
