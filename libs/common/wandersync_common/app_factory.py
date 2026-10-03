from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import structlog
from fastapi import APIRouter, Depends, FastAPI

from wandersync_common.config import ServiceSettings
from wandersync_common.db import Database
from wandersync_common.errors import register_exception_handlers
from wandersync_common.health import HealthCheck, health_router
from wandersync_common.logging import configure_logging
from wandersync_common.middleware import CorrelationIdMiddleware
from wandersync_common.security import internal_token_dependency

log = structlog.get_logger()

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_service_app(
    settings: ServiceSettings,
    db: Database,
    routers: Sequence[APIRouter] = (),
    extra_health_checks: Mapping[str, HealthCheck] | None = None,
    lifespan: Lifespan | None = None,
) -> FastAPI:
    """Crea la app FastAPI estándar de un microservicio de WanderSync.

    Incluye: logging JSON, X-Correlation-ID, formato de error del contrato,
    GET /health (público dentro de la red interna) y X-Internal-Token
    obligatorio en todos los `routers` del servicio.

    `lifespan` permite al servicio ejecutar lógica propia al arrancar o al
    apagarse (por ejemplo, la recuperación de SAGAs pendientes en orders-service).
    """
    configure_logging(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
        log.info("service_starting", environment=settings.environment)
        if lifespan is not None:
            async with lifespan(app):
                yield
        else:
            yield
        await db.dispose()
        log.info("service_stopped")

    app = FastAPI(
        title=settings.service_name,
        lifespan=app_lifespan,
        # La documentación OpenAPI solo existe en desarrollo.
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)

    checks: dict[str, HealthCheck] = {"database": db.ping, **(extra_health_checks or {})}
    app.include_router(health_router(checks))

    require_internal_token = Depends(internal_token_dependency(settings))
    for router in routers:
        app.include_router(router, dependencies=[require_internal_token])

    return app
