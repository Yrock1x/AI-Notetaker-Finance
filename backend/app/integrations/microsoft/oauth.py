"""Microsoft identity OAuth 2.0 — covers Teams, Outlook Calendar, and Meet
metadata via Microsoft Graph.

Uses the ``common`` tenant so both work and personal Microsoft accounts can
authenticate. For tenant-locked deployments switch ``common`` to the tenant
GUID. The shared flow lives in :mod:`app.integrations.oauth_flow`.
"""

from __future__ import annotations

from app.integrations import oauth_flow
from app.integrations.oauth_flow import OAuthProvider

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"  # noqa: S105 - public OAuth endpoint

# Delegated scopes for Microsoft 365 work/school accounts (Entra ID).
# OnlineMeetings.Read + Chat.Read only exist in the work/school universe;
# users on personal Microsoft accounts (outlook.com etc.) will fail here
# with invalid_scope — the right tradeoff for a B2B product.
#
# CallRecords.Read.All is intentionally NOT included: the Teams call-record
# webhook feature is deferred until a customer specifically needs it.
# Re-add it here and in the Azure app registration (Delegated, admin
# consent required) when you want /internal/microsoft/ensure-subscription
# to start creating live communications/callRecords subscriptions.
SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "email",
    "User.Read",
    "Calendars.Read",
    "OnlineMeetings.Read",
    "Chat.Read",
]

PROVIDER = OAuthProvider(
    name="microsoft",
    authorize_url=AUTHORIZE_URL,
    token_url=TOKEN_URL,
    scopes=SCOPES,
    client_id_setting="microsoft_client_id",
    client_secret_setting="microsoft_client_secret",  # noqa: S106 - settings attr name, not a secret
    send_scope_in_token_request=True,
    extra_authorize_params={"response_mode": "query", "prompt": "consent"},
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


async def refresh_microsoft(refresh_token: str) -> dict:
    return await oauth_flow.refresh(PROVIDER, refresh_token)
