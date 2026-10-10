import secrets
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import datetime, timezone
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wandersync_common.errors import AppError

from .config import settings
from .db import db
from .models import UserModel


router = APIRouter(tags=["Authentication"])
redis_client = aioredis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password.get_secret_value(),
    decode_responses=True,
)
password_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost_kib,
    parallelism=settings.argon2_parallelism,
)
dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class CreateSessionRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    previous_session_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None


async def get_async_session() -> AsyncIterator[AsyncSession]:
    # db.session es una dependencia (generador), no un context manager: se usa el sessionmaker.
    async with db.sessionmaker() as session:
        yield session


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    if len(payload.password) < settings.password_min_length:
        raise AppError(422, "VALIDATION_ERROR", "Password does not meet the minimum length")

    email = str(payload.email).strip().lower()
    full_name = payload.full_name.strip()
    if not full_name:
        raise AppError(422, "VALIDATION_ERROR", "Full name cannot be empty")

    existing_result = await session.execute(
        select(UserModel).where(UserModel.email == email)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists")

    user = UserModel(
        id=str(uuid4()),
        email=email,
        full_name=full_name,
        password_hash=password_hasher.hash(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists") from error

    return _user_data(user)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateSessionRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    email = str(payload.email).strip().lower()
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        _verify_dummy_password(payload.password)
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email or password")

    try:
        password_valid = password_hasher.verify(user.password_hash, payload.password)
    except VerifyMismatchError:
        password_valid = False
    if not password_valid:
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email or password")

    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(payload.password)
    now = int(time.time())
    user.last_login_at = datetime.fromtimestamp(now, tz=timezone.utc)
    await session.commit()

    if payload.previous_session_id:
        await _destroy_session(payload.previous_session_id)

    session_id = secrets.token_urlsafe(32)
    expires_at = now + settings.session_absolute_timeout_seconds
    session_key = f"session:{session_id}"
    sessions_key = f"user_sessions:{user.id}"
    async with redis_client.pipeline(transaction=True) as pipeline:
        pipeline.hset(
            session_key,
            mapping={
                "user_id": user.id,
                "created_at": str(now),
                "last_seen_at": str(now),
                "ip": payload.ip or "",
                "user_agent": payload.user_agent or "",
            },
        )
        pipeline.expire(session_key, settings.session_idle_timeout_seconds)
        pipeline.sadd(sessions_key, session_id)
        pipeline.expire(sessions_key, settings.session_absolute_timeout_seconds)
        await pipeline.execute()

    return {
        "session_id": session_id,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc),
        "user": _user_data(user),
    }


@router.get("/sessions/{session_id}")
async def validate_session(
    session_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    key = f"session:{session_id}"
    values = await redis_client.hgetall(key)
    if not values:
        raise AppError(404, "SESSION_NOT_FOUND", "The session does not exist")

    now = int(time.time())
    created_at = int(values["created_at"])
    expires_at = created_at + settings.session_absolute_timeout_seconds
    ttl = min(settings.session_idle_timeout_seconds, expires_at - now)
    if ttl <= 0:
        await _destroy_session(session_id, user_id=values["user_id"])
        raise AppError(404, "SESSION_NOT_FOUND", "The session does not exist")

    user_result = await session.execute(
        select(UserModel).where(UserModel.id == values["user_id"])
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        await _destroy_session(session_id, user_id=values["user_id"])
        raise AppError(404, "SESSION_NOT_FOUND", "The session does not exist")

    async with redis_client.pipeline(transaction=True) as pipeline:
        pipeline.hset(key, "last_seen_at", str(now))
        pipeline.expire(key, ttl)
        await pipeline.execute()
    return {
        "user": _user_data(user),
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc),
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> Response:
    await _destroy_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    result = await session.execute(
        select(UserModel).where(UserModel.id == str(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "The user does not exist")
    return _user_data(user)


def _verify_dummy_password(password: str) -> None:
    try:
        password_hasher.verify(dummy_password_hash, password)
    except VerifyMismatchError:
        pass


async def _destroy_session(session_id: str, *, user_id: str | None = None) -> None:
    key = f"session:{session_id}"
    owner = user_id or await redis_client.hget(key, "user_id")
    await redis_client.delete(key)
    if owner:
        sessions_key = f"user_sessions:{owner}"
        await redis_client.srem(sessions_key, session_id)
        if await redis_client.scard(sessions_key) == 0:
            await redis_client.delete(sessions_key)


def _user_data(user: UserModel) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": user.created_at,
    }
