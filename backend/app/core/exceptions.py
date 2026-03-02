import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class DealWiseError(Exception):
    """Base exception for all DealWise domain errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(DealWiseError):
    def __init__(self, resource: str, resource_id: str | None = None):
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} '{resource_id}' not found"
        super().__init__(message=detail, code="NOT_FOUND", status_code=404)


class PermissionDeniedError(DealWiseError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, code="PERMISSION_DENIED", status_code=403)


class ConflictError(DealWiseError):
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT", status_code=409)


class ValidationError(DealWiseError):
    def __init__(self, message: str):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)


class ExternalServiceError(DealWiseError):
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
        )


class RateLimitError(DealWiseError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, code="RATE_LIMIT", status_code=429)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(DealWiseError)
    async def dealwise_error_handler(request: Request, exc: DealWiseError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
