from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from wandersync_common import create_service_app

from .db import db
from .router import router
from .saga import recover_pending_sagas
from .config import settings
from .limiter import check_redis, redis_client


@asynccontextmanager
async def saga_lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await redis_client.ping()
    try:
        await recover_pending_sagas()
        _app.state.saga_recovery_complete = True
        yield
    finally:
        await redis_client.aclose()

app = create_service_app(
    settings=settings,
    db=db,
    routers=[router],
    extra_health_checks={"redis": check_redis},
    lifespan=saga_lifespan,
)