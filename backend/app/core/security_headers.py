"""Security-headers ASGI middleware.

Pure-ASGI (not BaseHTTPMiddleware) so it injects headers on the response-start
message without consuming the body stream — important because the worker serves
long-lived SSE streams (app/realtime/sse.py) and large FileResponse downloads
that must not be buffered.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import settings

Message = dict[str, Any]
Send = Callable[[Message], Awaitable[None]]
Receive = Callable[[], Awaitable[Message]]
Scope = dict[str, Any]

# (header, value) pairs applied to every response. HSTS + a strict CSP are
# production-only: CSP would block the dev-only Swagger UI at /docs, and HSTS is
# meaningless without TLS.
_BASE_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
]
_PROD_HEADERS: list[tuple[bytes, bytes]] = [
    (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
    (
        b"content-security-policy",
        b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    ),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        extra = list(_BASE_HEADERS)
        if settings.is_production:
            extra += _PROD_HEADERS

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {name.lower() for name, _ in headers}
                for name, value in extra:
                    if name not in present:
                        headers.append((name, value))
            await send(message)

        await self.app(scope, receive, send_with_headers)
