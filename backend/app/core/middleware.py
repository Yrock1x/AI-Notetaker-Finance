import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger(__name__)

# Paths that should not be audit logged
SKIP_AUDIT_PATHS = {"/health", "/health/ready", "/docs", "/redoc", "/openapi.json"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request for tracing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if not request.url.path.startswith("/health"):
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )

        return response


class OrgContextMiddleware(BaseHTTPMiddleware):
    """Extract organization context from request headers.

    Sets `request.state.org_id` for downstream use by dependencies.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        org_id = request.headers.get("X-Org-ID")
        if org_id:
            try:
                request.state.org_id = uuid.UUID(org_id)
            except ValueError:
                request.state.org_id = None  # Let dependency handle the validation error

        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Log every mutating API request to the audit_logs table.

    Captures: user_id, org_id, action (HTTP method + path), resource info,
    IP address, and user agent. Read-only requests (GET, HEAD, OPTIONS)
    are skipped for performance.
    """

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Only audit mutating requests on API paths
        if (
            request.method not in self.MUTATING_METHODS
            or request.url.path in SKIP_AUDIT_PATHS
            or not request.url.path.startswith("/api/")
        ):
            return response

        # Extract audit context from request state (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "org_id", None)

        if not user_id or not org_id:
            return response

        # Only audit successful operations
        if response.status_code >= 400:
            return response

        # Parse resource type and ID from the URL path
        resource_type, resource_id, deal_id = self._parse_resource(request.url.path)

        # Determine the action from HTTP method
        action = self._method_to_action(request.method, resource_type)

        # Log asynchronously — import here to avoid circular imports
        try:
            from app.core.database import async_session_factory
            from app.services.audit_service import AuditService

            async with async_session_factory() as session:
                audit_service = AuditService(db=session)
                await audit_service.log(
                    org_id=org_id,
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type or "",
                    resource_id=uuid.UUID(resource_id) if resource_id else None,
                    deal_id=uuid.UUID(deal_id) if deal_id else None,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get("User-Agent", ""),
                )
                await session.commit()
        except Exception:
            # Audit logging failures should never break the request
            logger.warning(
                "audit_log_failed",
                path=request.url.path,
                method=request.method,
            )

        return response

    @staticmethod
    def _parse_resource(path: str) -> tuple[str | None, str | None, str | None]:
        """Extract resource type, resource ID, and deal_id from a URL path.

        Examples:
            /api/v1/deals/uuid -> ('deal', 'uuid', 'uuid')
            /api/v1/deals/uuid/meetings/uuid -> ('meeting', 'uuid', 'deal-uuid')
            /api/v1/orgs/uuid -> ('organization', 'uuid', None)
        """
        parts = path.strip("/").split("/")
        # Remove 'api' and 'v1' prefix
        if len(parts) >= 2 and parts[0] == "api":
            parts = parts[2:]  # skip api/v1

        resource_type = None
        resource_id = None
        deal_id = None

        # Resource name mapping
        name_map = {
            "deals": "deal",
            "meetings": "meeting",
            "orgs": "organization",
            "documents": "document",
            "analyses": "analysis",
            "integrations": "integration",
            "admin": "admin",
            "qa": "qa",
            "transcript": "transcript",
        }

        i = 0
        while i < len(parts):
            segment = parts[i]
            if segment in name_map:
                resource_type = name_map[segment]
                if i + 1 < len(parts) and _is_uuid(parts[i + 1]):
                    resource_id = parts[i + 1]
                    if segment == "deals":
                        deal_id = resource_id
                    i += 2
                    continue
            i += 1

        return resource_type, resource_id, deal_id

    @staticmethod
    def _method_to_action(method: str, resource_type: str | None) -> str:
        """Convert HTTP method to an action string."""
        action_map = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }
        action = action_map.get(method, method.lower())
        if resource_type:
            return f"{action}_{resource_type}"
        return action

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Get the client IP, checking X-Forwarded-For for proxied requests."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


def _is_uuid(value: str) -> bool:
    """Check if a string looks like a UUID."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
