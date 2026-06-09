"""FastAPI dependencies — request auth + the shared LLM router.

Auth resolves the caller from a self-issued session token (cookie or bearer).
A Supabase-issued bearer JWT is also accepted while
``LEGACY_SUPABASE_AUTH_ENABLED`` is on, to keep the migration's rollback window
working; that path becomes dead code once the flag is permanently off.

Data access is owned by the SQLAlchemy layer (``app.db``); the worker no longer
exposes Supabase clients on the request path. The one-shot import script keeps
its own service-role client in ``app.db.migrate_from_supabase``.
"""

from __future__ import annotations

import time
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import Header, HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.llm.fireworks_provider import FireworksEmbeddingProvider, FireworksProvider
from app.llm.router import LLMRouter


# ---------------------------------------------------------------------------
# Auth user (decoded JWT claims)
# ---------------------------------------------------------------------------
class AuthUser(BaseModel):
    id: UUID
    email: str | None = None
    raw_claims: dict


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------
_jwks_cache: dict | None = None
_jwks_cache_ts: float = 0
_JWKS_TTL = 3600


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_cache_ts
    if _jwks_cache and (time.time() - _jwks_cache_ts) < _JWKS_TTL:
        return _jwks_cache
    if not settings.jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWKS URL is not configured",
        )
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(settings.jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_ts = time.time()
        return _jwks_cache


async def _verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued access token.

    Supabase supports two signing algorithms:

    - HS256 (legacy): signed with the shared ``SUPABASE_JWT_SECRET``. Simplest
      to verify but not exposed via JWKS.
    - RS256 / ES256 (current): signed with a rotating key published at the
      JWKS endpoint. We prefer this when available.

    We try JWKS first, fall back to HS256 if JWKS is empty or returns no
    matching kid — useful for local dev where only the anon secret is set.
    """
    try:
        headers = jwt.get_unverified_headers(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token"
        ) from exc

    kid = headers.get("kid")
    alg = headers.get("alg", "RS256")

    if kid and alg != "HS256":
        jwks = await _get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Signing key not found",
            )
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc

    # HS256 path (Supabase CLI in local dev, or hosted projects pre-JWKS).
    # Must verify against SUPABASE_JWT_SECRET — the anon key is not a signing
    # secret, and decoding without signature verification would let any HS256
    # token impersonate any user.
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HS256 token rejected: SUPABASE_JWT_SECRET not configured",
        )
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


# ---------------------------------------------------------------------------
# Dependency: current user from Authorization header
# ---------------------------------------------------------------------------
async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
) -> AuthUser:
    """Resolve the caller from (in order): a Bearer token, then the session cookie.

    A Bearer token is tried first as a self-issued session JWT, then as a Supabase
    JWT (transition compatibility). The session cookie is our self-issued token.
    """
    from app.auth.tokens import verify_session_token

    claims: dict | None = None
    token: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        claims = verify_session_token(token)  # self-issued?
        if claims is None and settings.legacy_supabase_auth_enabled:
            claims = await _verify_supabase_jwt(token)  # else Supabase (rollback window)
    else:
        cookie = request.cookies.get(settings.session_cookie_name)
        if cookie:
            claims = verify_session_token(cookie)

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing sub"
        )

    # Stash user_id so the rate limiter can key per-user (vs per-IP).
    request.state.user_id = sub
    return AuthUser(id=UUID(sub), email=claims.get("email"), raw_claims=claims)


# ---------------------------------------------------------------------------
# Dependency: LLM router
# ---------------------------------------------------------------------------
@lru_cache
def _build_llm_router() -> LLMRouter:
    r = LLMRouter()
    if settings.fireworks_api_key:
        r.register_provider("fireworks", FireworksProvider(settings.fireworks_api_key))
        r.register_embedding_provider(
            "fireworks", FireworksEmbeddingProvider(settings.fireworks_api_key)
        )
    if settings.premium_llm_enabled and settings.anthropic_api_key:
        from app.llm.claude_provider import ClaudeProvider

        r.register_provider("anthropic", ClaudeProvider(settings.anthropic_api_key))
    return r


def get_llm_router() -> LLMRouter:
    """Shared, cached LLM router. Fireworks is the default; Claude is opt-in
    via ``PREMIUM_LLM_ENABLED=true`` + ``ANTHROPIC_API_KEY``.
    """
    return _build_llm_router()
