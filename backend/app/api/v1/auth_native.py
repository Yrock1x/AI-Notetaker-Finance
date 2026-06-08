"""Self-hosted auth endpoints (OAuth login + session) — replaces Supabase Auth.

Flow: the browser hits /auth/login/{provider} → provider consent → the provider
redirects back to /auth/callback/{provider} → we provision the user, issue a
self-signed session JWT, set it as an httpOnly cookie, and bounce to the frontend.
The rest of the app reads that cookie via get_current_user.
"""

from __future__ import annotations

from typing import Literal

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.provisioning import get_or_create_user
from app.auth.tokens import DEFAULT_TTL_SECONDS, issue_session_token
from app.core.config import settings
from app.db.deps import get_db
from app.db.models import Profile
from app.dependencies import AuthUser, get_current_user
from app.schemas.common import BaseSchema

router = APIRouter()

# ---- OAuth client registry ------------------------------------------------
oauth = OAuth()
if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
if settings.microsoft_client_id:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        server_metadata_url=(
            "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )

_SUPPORTED = {"google", "microsoft"}


class SessionResponse(BaseSchema):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None


def _client(provider: str):
    if provider not in _SUPPORTED:
        raise HTTPException(status_code=404, detail="Unknown provider")
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider} OAuth is not configured",
        )
    return client


def _cookie_samesite() -> "Literal['lax', 'none']":
    # Frontend (vercel.app) and worker (fly.dev) are cross-site, so the session
    # cookie must be SameSite=None (+Secure) to ride the frontend's credentialed
    # fetches. Locally (http) fall back to lax since None requires Secure/https.
    return "none" if settings.is_production else "lax"


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=DEFAULT_TTL_SECONDS,
        httponly=True,
        secure=settings.is_production,
        samesite=_cookie_samesite(),
        path="/",
    )


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    client = _client(provider)
    redirect_uri = f"{settings.public_api_url}/api/v1/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, session: Session = Depends(get_db)):
    client = _client(provider)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth failed")
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await client.userinfo(token=token)
    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Provider returned no email")

    profile = get_or_create_user(
        session,
        email=email,
        full_name=userinfo.get("name"),
        avatar_url=userinfo.get("picture"),
    )
    session.commit()

    session_token = issue_session_token(profile.id, email)
    response = RedirectResponse(url=settings.frontend_url)
    _set_session_cookie(response, session_token)
    return response


@router.get("/session", response_model=SessionResponse)
def get_session(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> SessionResponse:
    profile = session.get(Profile, str(user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return SessionResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        avatar_url=profile.avatar_url,
    )


@router.post("/signout")
def signout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        samesite=_cookie_samesite(),
        secure=settings.is_production,
    )
    return response
