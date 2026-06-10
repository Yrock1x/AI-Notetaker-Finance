"""OAuth connect / callback / disconnect endpoints.

Three platforms currently supported:

- ``zoom``      — Zoom meetings + cloud recordings
- ``microsoft`` — Teams + Outlook + Calendar (one OAuth app)
- ``google``    — Google Calendar + Meet

The ``POST /connect`` endpoint returns an ``authorization_url`` that the SPA
redirects the browser to. ``GET /callback`` is called by the OAuth provider
after consent; it stores tokens and 302s back to ``FRONTEND_URL/integrations``.
``DELETE /disconnect`` soft-deletes the credential row.

Bot scheduling endpoints that used to live here were moved to
``/api/v1/internal/bot/*`` — the frontend talks to Supabase directly for
``meeting_bot_sessions`` CRUD and fires Inngest events from the browser.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.db.models import OrgMembership
from app.dependencies import AuthUser, get_current_user
from app.integrations.google import oauth as google_oauth
from app.integrations.microsoft import oauth as microsoft_oauth
from app.integrations.zoom import oauth as zoom_oauth
from app.services.oauth_tokens import (
    Platform,
    build_state,
    deactivate_credentials,
    list_user_integrations,
    redirect_uri_for,
    save_credentials,
    verify_state,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


SUPPORTED_PLATFORMS: set[Platform] = {"zoom", "microsoft", "google"}


def _assert_supported(platform: str) -> Platform:
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform '{platform}'",
        )
    return cast("Platform", platform)


def _resolve_default_org(session: Session, user_id: UUID) -> UUID:
    """Pick the user's first org membership as the default scope for the
    credential row. Users with multiple orgs are out of scope for v1 — they'll
    get tokens attached to whichever org comes back first."""
    org_id = session.scalar(
        select(OrgMembership.org_id)
        .where(OrgMembership.user_id == str(user_id))
        .limit(1)
    )
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no org membership; cannot connect integration",
        )
    return UUID(org_id)


# ---------------------------------------------------------------------------
# GET /api/v1/integrations
# ---------------------------------------------------------------------------


@router.get("")
async def list_integrations(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[dict]:
    return list_user_integrations(session, user_id=user.id)


# ---------------------------------------------------------------------------
# POST /api/v1/integrations/{platform}/connect
# ---------------------------------------------------------------------------


@router.post("/{platform}/connect")
async def initiate_oauth(
    platform: str,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict:
    p = _assert_supported(platform)
    org_id = _resolve_default_org(session, user.id)
    state = build_state(org_id, user.id, p)
    redirect_uri = redirect_uri_for(p)

    if p == "zoom":
        if not settings.zoom_client_id:
            raise HTTPException(500, "Zoom OAuth is not configured")
        url = zoom_oauth.build_authorize_url(
            client_id=settings.zoom_client_id,
            redirect_uri=redirect_uri,
            state=state,
        )
    elif p == "microsoft":
        if not settings.microsoft_client_id:
            raise HTTPException(500, "Microsoft OAuth is not configured")
        url = microsoft_oauth.build_authorize_url(
            client_id=settings.microsoft_client_id,
            redirect_uri=redirect_uri,
            state=state,
        )
    elif p == "google":
        if not settings.google_client_id:
            raise HTTPException(500, "Google OAuth is not configured")
        url = google_oauth.build_authorize_url(
            client_id=settings.google_client_id,
            redirect_uri=redirect_uri,
            state=state,
        )
    else:  # pragma: no cover - guarded above
        raise HTTPException(400, f"Unsupported platform {p}")

    logger.info("oauth_connect_initiated", platform=p, user_id=str(user.id))
    return {"authorization_url": url}


# ---------------------------------------------------------------------------
# GET /api/v1/integrations/{platform}/callback
# ---------------------------------------------------------------------------


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    p = _assert_supported(platform)
    frontend = (settings.frontend_url or "http://localhost:3000").rstrip("/")
    return_to = f"{frontend}/integrations"

    if error:
        logger.warning("oauth_callback_provider_error", platform=p, error=error)
        return RedirectResponse(
            url=f"{return_to}?error={error}", status_code=302
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state in OAuth callback")

    try:
        claims = verify_state(state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if claims.get("platform") != p:
        raise HTTPException(400, "OAuth state platform mismatch")

    org_id = UUID(claims["org_id"])
    user_id = UUID(claims["user_id"])
    redirect_uri = redirect_uri_for(p)

    if p == "zoom":
        tokens = await zoom_oauth.exchange_code(
            client_id=settings.zoom_client_id,
            client_secret=settings.zoom_client_secret,
            redirect_uri=redirect_uri,
            code=code,
        )
    elif p == "microsoft":
        tokens = await microsoft_oauth.exchange_code(
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            redirect_uri=redirect_uri,
            code=code,
        )
    elif p == "google":
        tokens = await google_oauth.exchange_code(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=redirect_uri,
            code=code,
        )
    else:  # pragma: no cover
        raise HTTPException(400, f"Unsupported platform {p}")

    save_credentials(
        session,
        org_id=org_id,
        user_id=user_id,
        platform=p,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in_seconds=tokens.get("expires_in"),
        scopes=tokens.get("scope"),
    )

    return RedirectResponse(url=f"{return_to}?connected={p}", status_code=302)


# ---------------------------------------------------------------------------
# DELETE /api/v1/integrations/{platform}/disconnect
# ---------------------------------------------------------------------------


@router.delete("/{platform}/disconnect", status_code=204)
async def disconnect_integration(
    platform: str,
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    p = _assert_supported(platform)
    org_id = _resolve_default_org(session, user.id)
    deactivate_credentials(session, org_id=org_id, user_id=user.id, platform=p)
    logger.info("oauth_disconnected", platform=p, user_id=str(user.id))
