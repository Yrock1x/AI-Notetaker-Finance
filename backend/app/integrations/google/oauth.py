"""Google OAuth 2.0 for Calendar + Meet.

Google does NOT return a refresh_token on every authorize — only on the first
consent, or if ``access_type=offline`` + ``prompt=consent`` force re-issue.
We always set both to guarantee we get one; callers should persist the
existing refresh token if the refresh response omits it.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public OAuth endpoint

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
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
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "google_code_exchange_failed",
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


async def refresh_google(refresh_token: str) -> dict:
    from app.core.config import settings

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "google_refresh_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()
        # Google omits refresh_token on refresh responses; callers must
        # fall back to the stored one.
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope"),
        }
