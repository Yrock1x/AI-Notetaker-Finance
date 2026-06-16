"""Self-issued session JWTs (replaces Supabase-issued tokens).

HS256 signed with ``settings.session_jwt_secret`` (falling back to other configured
secrets in dev). Carries the same ``sub``/``email`` shape the rest of the app
already reads, so downstream code is unchanged.
"""

from __future__ import annotations

import time

from jose import JWTError, jwt

from app.core.config import settings

ISSUER = "cognisuite-worker"
ALGORITHM = "HS256"
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _secret() -> str:
    if settings.session_jwt_secret:
        return settings.session_jwt_secret
    # Outside production only, fall back to the internal token so local dev /
    # tests work without a dedicated SESSION_JWT_SECRET. Production boot requires
    # SESSION_JWT_SECRET (config._require_prod_secrets), so the shared internal
    # token is never silently used to sign sessions in prod.
    if not settings.is_production and settings.worker_internal_token:
        return settings.worker_internal_token
    raise RuntimeError(
        "No session signing secret configured (set SESSION_JWT_SECRET)"
    )


def issue_session_token(
    user_id: str, email: str | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(user_id),
        "email": email,
        "iss": ISSUER,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def verify_session_token(token: str) -> dict | None:
    """Return claims for a valid self-issued token, else None."""
    try:
        return jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"verify_aud": False},
        )
    except JWTError:
        return None
