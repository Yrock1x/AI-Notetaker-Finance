"""Zoom OAuth 2.0 authentication flow.

Zoom uses HTTP Basic authentication (base64 of client_id:client_secret) on
the token endpoint, which differs from the form-encoded client credentials
used by Microsoft and Slack.
"""

from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger(__name__)

ZOOM_AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"


class ZoomOAuth:
    """Handles Zoom OAuth 2.0 authentication flow."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        """Initialize the Zoom OAuth client with app credentials."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def _basic_auth_header(self) -> str:
        """Return the Base64-encoded ``client_id:client_secret`` for Basic auth."""
        raw = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(raw.encode()).decode()

    def get_authorization_url(self, state: str) -> str:
        """Generate the Zoom OAuth authorization URL for user consent."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{ZOOM_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for access and refresh tokens.

        Returns a dict with ``access_token``, ``refresh_token``,
        ``expires_in``, ``scope``, and ``token_type``.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    ZOOM_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                    headers={
                        "Authorization": f"Basic {self._basic_auth_header()}",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    "zoom_code_exchanged",
                    scope=data.get("scope"),
                    expires_in=data.get("expires_in"),
                )
                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token"),
                    "expires_in": data.get("expires_in"),
                    "scope": data.get("scope", ""),
                    "token_type": data.get("token_type", "bearer"),
                }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "zoom_code_exchange_failed",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("zoom_code_exchange_network_error", error=str(exc))
            raise

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token using a refresh token.

        Returns a dict with ``access_token``, ``refresh_token``,
        ``expires_in``, ``scope``, and ``token_type``.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    ZOOM_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    headers={
                        "Authorization": f"Basic {self._basic_auth_header()}",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    "zoom_token_refreshed",
                    scope=data.get("scope"),
                    expires_in=data.get("expires_in"),
                )
                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token"),
                    "expires_in": data.get("expires_in"),
                    "scope": data.get("scope", ""),
                    "token_type": data.get("token_type", "bearer"),
                }
        except httpx.HTTPStatusError as exc:
            logger.error(
                "zoom_token_refresh_failed",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("zoom_token_refresh_network_error", error=str(exc))
            raise
