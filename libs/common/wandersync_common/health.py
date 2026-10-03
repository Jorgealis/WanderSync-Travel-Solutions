import asyncio
from collections.abc import Awaitable, Callable, Mapping

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = structlog.get_logger()

HealthCheck = Callable[[], Awaitable[None]]


def health_router(checks: Mapping[str, HealthCheck], timeout_seconds: float = 2.0) -> APIRouter:
    """GET /health: 200 si todas las dependencias responden, 503 si alguna falla.

    Es lo que consulta el healthcheck de Docker Compose, por lo que
    `depends_on: condition: service_healthy` espera a que la BD esté accesible.
    """
    router = APIRouter()

    @router.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        results: dict[str, str] = {}
        for name, check in checks.items():
            try:
                await asyncio.wait_for(check(), timeout=timeout_seconds)
                results[name] = "up"
            except Exception as exc:
                log.warning("health_check_failed", dependency=name, error=type(exc).__name__)
                results[name] = "down"

        healthy = all(status == "up" for status in results.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "degraded", "checks": results},
        )

    return router
