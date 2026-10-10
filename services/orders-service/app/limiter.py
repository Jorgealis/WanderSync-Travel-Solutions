import hashlib

import redis.asyncio as aioredis
from fastapi import Response

from .config import settings
from wandersync_common.errors import AppError


redis_client = aioredis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password.get_secret_value(),
    decode_responses=True,
)

_INCREMENT_WITH_TTL = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""

_PERIOD_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


async def check_redis() -> None:
    await redis_client.ping()


async def enforce_payment_rate_limit(user_id: str, response: Response) -> None:
    limit, period = _parse_policy(settings.rate_limit_payment)
    user_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    count, ttl = await redis_client.eval(
        _INCREMENT_WITH_TTL,
        1,
        f"rate-limit:orders:{user_hash}",
        period,
    )
    if int(count) <= limit:
        return

    retry_after = max(int(ttl), 1)
    response.headers["Retry-After"] = str(retry_after)
    raise AppError(
        429,
        "RATE_LIMITED",
        "Payment rate limit exceeded",
        {"retry_after": retry_after},
    )


def _parse_policy(policy: str) -> tuple[int, int]:
    try:
        count_text, period_text = policy.split("/", maxsplit=1)
        count = int(count_text)
        seconds = _PERIOD_SECONDS[period_text.rstrip("s").lower()]
    except (ValueError, KeyError) as error:
        raise ValueError(f"Invalid payment rate-limit policy: {policy!r}") from error
    if count <= 0:
        raise ValueError(f"Invalid payment rate-limit count: {policy!r}")
    return count, seconds
