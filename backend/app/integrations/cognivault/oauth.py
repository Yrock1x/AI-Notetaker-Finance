"""CogniVault OAuth — this worker is an OAuth *client* of CogniVault.

The "Connect a deal to a VDR" flow: we redirect the user to CogniVault's authorize
endpoint (passing the deal context as ``deal_ref``/``deal_name``). CogniVault
authenticates the user, **enforces on its own consent screen that the user admins
the chosen VDR**, and redirects back with a ``code``. We exchange the code and read
the chosen ``vdr_id`` (and optional ``vdr_name``) from the token response — that's
the one field beyond the standard OAuth set we depend on.

Authorize-URL building reuses :mod:`app.integrations.oauth_flow`; the token
exchange is bespoke only because it surfaces ``vdr_id`` (the shared helper drops
non-standard body fields).
"""

from __future__ import annotations

import httpx
import structlog

from app.core.config import settings
from app.integrations import oauth_flow
from app.integrations.oauth_flow import OAuthProvider

logger = structlog.get_logger(__name__)

SCOPES = ["vdr.share"]


def is_configured() -> bool:
    return bool(
        settings.cognivault_client_id
        and settings.cognivault_client_secret
        and settings.cognivault_authorize_url
        and settings.cognivault_token_url
    )


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str, deal_id: str, deal_name: str | None = None
) -> str:
    """Authorize URL with the deal context attached so CogniVault can label the
    consent screen and pre-associate the VDR with this deal."""
    extra: dict[str, str] = {"deal_ref": deal_id}
    if deal_name:
        extra["deal_name"] = deal_name
    provider = OAuthProvider(
        name="cognivault",
        authorize_url=settings.cognivault_authorize_url,
        token_url=settings.cognivault_token_url,
        scopes=SCOPES,
        client_id_setting="cognivault_client_id",
        client_secret_setting="cognivault_client_secret",  # noqa: S106 - settings attr name
        extra_authorize_params=extra,
    )
    return oauth_flow.build_authorize_url(
        provider, client_id=client_id, redirect_uri=redirect_uri, state=state
    )


async def exchange_code(
    *, client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    """Exchange the authorization code for tokens + the chosen ``vdr_id``."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.cognivault_token_url, data=data)
        if resp.status_code >= 400:
            logger.error(
                "cognivault_token_request_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            resp.raise_for_status()
        body = resp.json()
    return {
        "access_token": body.get("access_token"),
        "refresh_token": body.get("refresh_token"),
        "expires_in": body.get("expires_in"),
        "scope": body.get("scope"),
        "vdr_id": body.get("vdr_id"),
        "vdr_name": body.get("vdr_name"),
    }
