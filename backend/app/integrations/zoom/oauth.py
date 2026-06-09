"""Zoom OAuth 2.0.

Zoom uses HTTP Basic auth (base64 of client_id:client_secret) on the token
endpoint, unlike Microsoft/Google which accept form-encoded credentials. It
also omits ``scope`` on the authorize URL — see PROVIDER below. The shared flow
lives in :mod:`app.integrations.oauth_flow`.
"""

from __future__ import annotations

from app.integrations import oauth_flow
from app.integrations.oauth_flow import OAuthProvider

AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"  # noqa: S105 - public OAuth endpoint

# Scopes needed for calendar sync + cloud-recording webhook ingest.
SCOPES = ["user:read", "meeting:read", "recording:read"]

# No ``scope`` param on the authorize URL — Zoom defaults to granting every
# scope configured on the app in the marketplace UI. Passing explicit legacy
# scope names fails with invalid_scope against apps using the newer granular
# scope system; leaving it out lets either scope style work.
PROVIDER = OAuthProvider(
    name="zoom",
    authorize_url=AUTHORIZE_URL,
    token_url=TOKEN_URL,
    scopes=SCOPES,
    client_id_setting="zoom_client_id",
    client_secret_setting="zoom_client_secret",  # noqa: S106 - settings attr name, not a secret
    use_basic_auth=True,
    include_scope_in_authorize=False,
)


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    return oauth_flow.build_authorize_url(
        PROVIDER, client_id=client_id, redirect_uri=redirect_uri, state=state
    )


async def exchange_code(
    *, client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    return await oauth_flow.exchange_code(
        PROVIDER,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        code=code,
    )


async def refresh_zoom(refresh_token: str) -> dict:
    return await oauth_flow.refresh(PROVIDER, refresh_token)
