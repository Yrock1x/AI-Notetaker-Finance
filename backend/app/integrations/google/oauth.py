"""Google OAuth 2.0 for Calendar + Meet.

Google does NOT return a refresh_token on every authorize — only on the first
consent, or if ``access_type=offline`` + ``prompt=consent`` force re-issue.
We always set both to guarantee we get one; callers should persist the
existing refresh token if the refresh response omits it. The shared flow lives
in :mod:`app.integrations.oauth_flow`.
"""

from __future__ import annotations

from app.integrations import oauth_flow
from app.integrations.oauth_flow import OAuthProvider

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public OAuth endpoint

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]

PROVIDER = OAuthProvider(
    name="google",
    authorize_url=AUTHORIZE_URL,
    token_url=TOKEN_URL,
    scopes=SCOPES,
    client_id_setting="google_client_id",
    client_secret_setting="google_client_secret",  # noqa: S106 - settings attr name, not a secret
    extra_authorize_params={
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    },
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


async def refresh_google(refresh_token: str) -> dict:
    return await oauth_flow.refresh(PROVIDER, refresh_token)
