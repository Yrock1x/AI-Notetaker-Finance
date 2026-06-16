from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.core.security_headers import SecurityHeadersMiddleware


def _init_sentry() -> None:
    """Initialize Sentry if a DSN is configured. No-op if sentry-sdk isn't installed."""
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    _init_sentry()
    # Fail fast on a misconfigured LLM routing table (missing provider keys,
    # malformed model override). Prod-only: dev/test run without provider keys
    # and shouldn't crash on boot — a task with no provider raises clearly on
    # first use instead.
    if settings.is_production:
        from app.dependencies import get_llm_router

        get_llm_router().validate_routing()
    yield


def create_app() -> FastAPI:
    """FastAPI factory — slim LLM + webhook worker.

    Data access is owned by the SQLAlchemy layer (``app.db``); request auth and
    the shared LLM router are provided via DI in ``app.dependencies``.
    """
    app = FastAPI(
        title=settings.app_name,
        description="CogniSuite worker — LLM, webhooks, live transcription",
        version="0.2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # Security headers on every response (nosniff / frame-deny / referrer +
    # HSTS & CSP in prod). Pure-ASGI so it doesn't buffer SSE / file downloads.
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # Pattern-based allow for environments where the Origin isn't known
        # at deploy time (Vercel preview URLs, branch deployments). If unset
        # the regex is None and only the explicit list applies.
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        # Narrow to the verbs + headers the frontend actually sends. Wildcards
        # work but expose every future route to every method, which makes
        # CSRF audits harder to reason about.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Internal-Token",
            "X-Requested-With",
        ],
    )

    # Per-user rate limiting. Routes opt in via @limiter.limit("...").
    # The middleware materialises the limit-per-request hooks; the
    # exception handler converts RateLimitExceeded into a 429 response.
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Session middleware — used by Authlib to hold the OAuth state between
    # /auth/login and /auth/callback. Secret reuses a configured signing key.
    from starlette.middleware.sessions import SessionMiddleware

    app.add_middleware(
        SessionMiddleware,
        secret_key=(
            settings.session_jwt_secret
            or settings.worker_internal_token
            or "dev-only-session-secret"
        ),
        same_site="lax",
        https_only=settings.is_production,
    )

    register_exception_handlers(app)

    # App-layer tenant-scope violations (store routers) → 403.
    from app.api.v1.store._common import access_denied_handler
    from app.db.scope import AccessDenied

    app.add_exception_handler(AccessDenied, access_denied_handler)

    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    # CogniVault partner API (M2M, separate /partner/v1 namespace).
    from app.api.v1.partner.router import router as partner_router

    app.include_router(partner_router, tags=["Partner (CogniVault)"])
    return app
