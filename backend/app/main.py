from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    AuditLogMiddleware,
    OrgContextMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    setup_logging()
    yield
    # Shutdown: dispose database engine connection pool
    from app.core.database import engine
    await engine.dispose()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.app_name,
        description="Meeting intelligence platform for investment professionals",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (add_middleware stacks in reverse — last added runs outermost)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(OrgContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    return app
