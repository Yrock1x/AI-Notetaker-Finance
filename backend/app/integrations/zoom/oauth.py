"""Zoom OAuth 2.0.

Zoom uses HTTP Basic auth (base64 of client_id:client_secret) on the token
endpoint, unlike Microsoft/Google which accept form-encoded credentials.
"""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger(__name__)

AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"  # noqa: S105 - public OAuth endpoint

# Scopes needed for calendar sync + cloud-recording webhook ingest.
SCOPES = ["user:read", "meeting:read", "recording:read"]


def _basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return base64.b64encode(raw).decode()


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str
) -> str:
    # No ``scope`` param — Zoom defaults to granting every scope configured
    # on the app in the marketplace UI. Passing explicit legacy scope names
    # (``user:read``, ``meeting:read``, ``recording:read``) fails with
    # invalid_scope against apps that use the newer granular scope system
    # (``user:read:user``, ``meeting:read:list_user_meetings`` etc). Keeping
    # it out of the URL lets either scope style work.
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
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
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Authorization": f"Basic {_basic_auth(client_id, client_secret)}",
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "zoom_code_exchange_failed",
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
            "token_type": data.get("token_type", "bearer"),
        }


async def refresh_zoom(refresh_token: str) -> dict:
    from app.core.config import settings

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={
                "Authorization": (
                    f"Basic {_basic_auth(settings.zoom_client_id, settings.zoom_client_secret)}"
                ),
            },
        )
        if resp.status_code >= 400:
            logger.error(
                "zoom_refresh_failed",
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


# ---------------------------------------------------------------------------
# Backwards-compatible class wrapper. A few legacy callers still expect a
# ``ZoomOAuth`` instance; prefer the module-level functions in new code.
# ---------------------------------------------------------------------------


class ZoomOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        return build_authorize_url(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            state=state,
        )

    async def exchange_code(self, code: str) -> dict:
        return await exchange_code(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            code=code,
        )

    async def refresh_token(self, refresh_token: str) -> dict:
        return await refresh_zoom(refresh_token)
