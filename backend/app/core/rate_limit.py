"""Per-user rate limiting for expensive endpoints (LLM-backed Q&A and
analysis).

Cost-DoS context: a single authenticated user can rack up thousands of
dollars in Fireworks/Claude tokens by spamming /qa or /analysis. slowapi
gives us per-user buckets so one tenant can't exhaust the LLM budget for
the whole platform.

Keying strategy: prefer the verified ``request.state.user_id`` (set by
``get_current_user`` after JWT verification). For unauthenticated routes
that ever opt in to limiting, fall back to client IP. Fall back to the
literal "anon" only if neither is available (effectively a global bucket
— better than no limit).
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def user_or_ip_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    ip = get_remote_address(request)
    return f"ip:{ip}" if ip else "anon"


# Single shared limiter. Routes opt in via @limiter.limit("...") decorators;
# nothing is rate-limited by default.
limiter = Limiter(key_func=user_or_ip_key)
