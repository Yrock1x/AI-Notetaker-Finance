"""Shared OAuth 2.0 authorization-code flow.

Zoom, Microsoft, and Google differ only in a few knobs (Basic-auth token
endpoint vs. form-encoded credentials, whether scope is sent on the authorize
URL / token request, and provider-specific authorize params). This module
captures the common build-URL / exchange-code / refresh logic once; each
provider module declares an :class:`OAuthProvider` and exposes thin,
back-compatible wrappers over the functions here.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class OAuthProvider:
    name: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    # Settings attribute names for the client credentials (read lazily so the
    # refresh path doesn't need them plumbed through).
    client_id_setting: str
    client_secret_setting: str
    # Zoom authenticates the token endpoint with an HTTP Basic header instead
    # of client_id/client_secret in the form body.
    use_basic_auth: bool = False
    # Zoom omits ``scope`` on the authorize URL (it grants whatever the app is
    # configured for); Microsoft/Google send it.
    include_scope_in_authorize: bool = True
    # Microsoft echoes ``scope`` back in token/refresh requests; Google/Zoom don't.
    send_scope_in_token_request: bool = False
    # Provider-specific authorize-URL params (response_mode, prompt, access_type…).
    extra_authorize_params: dict[str, str] = field(default_factory=dict)

    def _client_credentials(self) -> tuple[str, str]:
        from app.core.config import settings

        return (
            getattr(settings, self.client_id_setting),
            getattr(settings, self.client_secret_setting),
        )


def _basic_auth(client_id: str, client_secret: str) -> str:
    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def build_authorize_url(
    provider: OAuthProvider, *, client_id: str, redirect_uri: str, state: str
) -> str:
    params: dict[str, str] = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    if provider.include_scope_in_authorize:
        params["scope"] = " ".join(provider.scopes)
    params.update(provider.extra_authorize_params)
    return f"{provider.authorize_url}?{urlencode(params)}"


async def _post_token(
    provider: OAuthProvider, data: dict, *, client_id: str, client_secret: str
) -> dict:
    """POST to the token endpoint with the provider's auth style and parse the
    standard token response (raises on HTTP >= 400 after logging)."""
    headers: dict[str, str] = {}
    if provider.use_basic_auth:
        headers["Authorization"] = f"Basic {_basic_auth(client_id, client_secret)}"
    else:
        data = {**data, "client_id": client_id, "client_secret": client_secret}
    if provider.send_scope_in_token_request:
        data = {**data, "scope": " ".join(provider.scopes)}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(provider.token_url, data=data, headers=headers)
        if resp.status_code >= 400:
            logger.error(
                f"{provider.name}_token_request_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        body = resp.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token"),
        "expires_in": body.get("expires_in"),
        "scope": body.get("scope"),
        "token_type": body.get("token_type", "Bearer"),
        "id_token": body.get("id_token"),
    }


async def exchange_code(
    provider: OAuthProvider, *, client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    return await _post_token(
        provider,
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        client_id=client_id,
        client_secret=client_secret,
    )


async def refresh(provider: OAuthProvider, refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token. Reads client creds from
    settings. (Google omits ``refresh_token`` on refresh responses — callers
    must fall back to the stored one.)"""
    client_id, client_secret = provider._client_credentials()
    return await _post_token(
        provider,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
        client_id=client_id,
        client_secret=client_secret,
    )
