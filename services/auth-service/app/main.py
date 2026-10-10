from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from wandersync_common import create_service_app

from .config import settings
from .db import db
from .router import router
from .router import redis_client


@asynccontextmanager
async def auth_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.redis_client = redis_client
    try:
        await redis_client.ping()
        yield
    finally:
        await redis_client.aclose()


async def check_redis() -> None:
    await redis_client.ping()


app = create_service_app(
    settings=settings,
    db=db,
    routers=[router],
    extra_health_checks={"redis": check_redis},
    lifespan=auth_lifespan,
)