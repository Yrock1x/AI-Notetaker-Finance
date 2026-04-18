from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging


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
    yield


def create_app() -> FastAPI:
    """FastAPI factory — slim LLM + webhook worker.

    No database session middleware: all DB access goes through Supabase
    clients obtained via DI in ``app.dependencies``.
    """
    app = FastAPI(
        title=settings.app_name,
        description="DealWise AI worker — LLM, webhooks, live transcription",
        version="0.2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
        redirect_slashes=False,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")
    return app
