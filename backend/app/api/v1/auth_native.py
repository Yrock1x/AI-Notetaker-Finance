"""Self-hosted auth endpoints (OAuth login + session) — replaces Supabase Auth.

Flow: the browser hits /auth/login/{provider} → provider consent → the provider
redirects back to /auth/callback/{provider} → we provision the user, issue a
self-signed session JWT, set it as an httpOnly cookie, and bounce to the frontend.
The rest of the app reads that cookie via get_current_user.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlencode

import structlog
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    hash_password,
    verify_password,
)
from app.auth.provisioning import get_or_create_user
from app.auth.tokens import DEFAULT_TTL_SECONDS, issue_session_token
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.db.models import Profile
from app.dependencies import AuthUser, get_current_user
from app.schemas.common import BaseSchema

logger = structlog.get_logger(__name__)

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


class RegisterRequest(BaseSchema):
    email: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseSchema):
    email: str
    password: str


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


def _cookie_samesite() -> Literal['lax', 'none']:
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


def _safe_next(path: str | None) -> str:
    """Only allow same-site relative paths (guard against open redirect)."""
    if not path or not path.startswith("/") or path.startswith("//"):
        return "/dashboard"
    return path


def _session_cookie_response(profile: Profile) -> JSONResponse:
    """Mint a session for ``profile`` and return it as a cookie-bearing JSON body.

    Used by the email/password endpoints, which are fetch() calls (not
    navigations), so they return JSON + Set-Cookie rather than a redirect.
    """
    token = issue_session_token(profile.id, profile.email)
    body = SessionResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        avatar_url=profile.avatar_url,
    )
    response = JSONResponse(body.model_dump())
    _set_session_cookie(response, token)
    return response


def _login_error_redirect(message: str) -> RedirectResponse:
    """Bounce a failed OAuth callback back to the frontend login page.

    Returning a raw JSON error here would strand the user on the worker domain
    (the classic "stuck on an error page"); a 302 to /login?error=… returns them
    to a usable screen that renders ``message``.
    """
    query = urlencode({"error": message})
    return RedirectResponse(url=f"{settings.frontend_url.rstrip('/')}/login?{query}")


def _normalize_email(raw: str) -> str:
    email = (raw or "").strip()
    # Deliberately lenient: a single "@" with text on both sides + a length cap.
    # The provider/registration is the source of truth, not a strict RFC regex.
    local, _, domain = email.partition("@")
    if not local or not domain or len(email) > 320:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return email


def _validate_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Password must be between {MIN_PASSWORD_LENGTH} and "
                f"{MAX_PASSWORD_LENGTH} characters."
            ),
        )


@router.get("/login/{provider}")
async def login(provider: str, request: Request, next: str = "/dashboard"):  # noqa: A002 — `next` is the public query-param name
    client = _client(provider)
    # Stash where to land the user after callback (survives the round-trip via
    # the Authlib session cookie). Sanitized on the way out.
    request.session["post_login_next"] = _safe_next(next)
    redirect_uri = f"{settings.public_api_url}/api/v1/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, session: Session = Depends(get_db)):
    # Every failure below returns the user to /login?error=… (a usable page)
    # instead of raising a raw JSON error that strands them on the worker domain.
    try:
        client = _client(provider)
    except HTTPException:
        return _login_error_redirect("Sign-in isn't available right now. Please try again later.")

    # Microsoft's `common` OIDC metadata declares a templated issuer
    # (https://login.microsoftonline.com/{tenantid}/v2.0), so exact id_token
    # issuer validation fails. Suppress ONLY the iss check for Microsoft —
    # signature, audience (client_id), expiry, and nonce are still enforced.
    extra: dict = {"claims_options": {"iss": {}}} if provider == "microsoft" else {}
    try:
        token = await client.authorize_access_token(request, **extra)
    except OAuthError as err:
        logger.warning("oauth_callback_failed", provider=provider, error=str(err))
        return _login_error_redirect("We couldn't complete sign-in. Please try again.")

    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = await client.userinfo(token=token)
        except Exception as err:  # noqa: BLE001 — any failure here is "couldn't read profile"
            logger.warning("oauth_userinfo_failed", provider=provider, error=str(err))
            return _login_error_redirect("We couldn't read your profile from the provider.")

    # Microsoft id_tokens frequently omit `email`; the UPN in
    # `preferred_username` is the user's email in practice.
    email = userinfo.get("email") or userinfo.get("preferred_username")
    if not email:
        return _login_error_redirect("Your provider didn't share an email address.")

    profile = get_or_create_user(
        session,
        email=email,
        full_name=userinfo.get("name"),
        avatar_url=userinfo.get("picture"),
    )
    try:
        session.commit()
    except IntegrityError:
        # Concurrent first-login for the same email: another request won the
        # insert. Roll back and adopt the existing profile.
        session.rollback()
        existing = session.scalar(
            select(Profile).where(func.lower(Profile.email) == email.lower())
        )
        if existing is None:
            return _login_error_redirect("Sign-in failed. Please try again.")
        profile = existing

    next_path = _safe_next(request.session.pop("post_login_next", "/dashboard"))
    session_token = issue_session_token(profile.id, email)
    response = RedirectResponse(url=settings.frontend_url.rstrip("/") + next_path)
    _set_session_cookie(response, session_token)
    return response


# ---- email / password (local accounts) ------------------------------------
# These are credentialed fetch() calls, so CSRF is handled the same way as
# every other state-changing endpoint: the CORS layer (main.py) only allows our
# own origins to send credentialed requests, and the JSON content-type forces a
# preflight a third-party page can't satisfy. They return JSON + Set-Cookie.


@router.post("/register")
@limiter.limit("10/hour")
def register(
    request: Request, payload: RegisterRequest, session: Session = Depends(get_db)
) -> JSONResponse:
    email = _normalize_email(payload.email)
    _validate_password(payload.password)

    existing = session.scalar(
        select(Profile).where(func.lower(Profile.email) == email.lower())
    )
    if existing is not None:
        # The email is already taken — whether by a password account or an
        # OAuth one. We do NOT set a password on a pre-existing account here:
        # without proof of email ownership that would be account takeover. The
        # user can reach an OAuth account via its provider button instead.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try signing in instead.",
        )

    profile = get_or_create_user(session, email=email, full_name=payload.full_name)
    profile.password_hash = hash_password(payload.password)
    try:
        session.commit()
    except IntegrityError:
        # Lost a race with a concurrent signup for the same email.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try signing in instead.",
        ) from None

    logger.info("local_account_registered", email=email)
    return _session_cookie_response(profile)


@router.post("/login")
@limiter.limit("10/minute")
def login_password(
    request: Request, payload: LoginRequest, session: Session = Depends(get_db)
) -> JSONResponse:
    email = _normalize_email(payload.email)
    profile = session.scalar(
        select(Profile).where(func.lower(Profile.email) == email.lower())
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if profile.password_hash is None:
        # The account exists but has no local credential → it's OAuth-only.
        # Point the user at the right button rather than failing opaquely.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account uses Google or Microsoft sign-in. Please use those buttons.",
        )

    if not verify_password(payload.password, profile.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled.",
        )

    return _session_cookie_response(profile)


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
