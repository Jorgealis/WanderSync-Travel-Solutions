import re
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = "X-Correlation-ID"

# Solo se aceptan IDs entrantes "seguros" para evitar inyección en los logs.
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

log = structlog.get_logger()


def current_correlation_id() -> str | None:
    return correlation_id_var.get()


class CorrelationIdMiddleware:
    """Propaga X-Correlation-ID y registra una línea de log por petición.

    Middleware ASGI puro (no BaseHTTPMiddleware) para que el contextvar sea
    visible en los endpoints y en las tareas que estos lancen.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(CORRELATION_HEADER.lower().encode(), b"")
        correlation_id = incoming.decode("latin-1")
        if not _VALID_CORRELATION_ID.match(correlation_id):
            correlation_id = str(uuid.uuid4())

        token = correlation_id_var.set(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((CORRELATION_HEADER.encode(), correlation_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            if scope["path"] != "/health":
                log.info(
                    "http_request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            structlog.contextvars.unbind_contextvars("correlation_id")
            correlation_id_var.reset(token)
