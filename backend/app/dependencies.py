"""FastAPI dependencies — request auth + the shared LLM router.

Auth resolves the caller from a self-issued session token (cookie or bearer).
Data access is owned by the SQLAlchemy layer (``app.db``).
"""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from fastapi import Header, HTTPException, Request, status
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
# Dependency: current user from Authorization header / session cookie
# ---------------------------------------------------------------------------
async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
) -> AuthUser:
    """Resolve the caller from a self-issued session token: a Bearer token if
    present, otherwise the session cookie."""
    from app.auth.tokens import verify_session_token

    claims: dict | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        claims = verify_session_token(token)
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
