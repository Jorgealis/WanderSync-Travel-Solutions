import hashlib
from typing import Any

import redis.asyncio as aioredis
from graphql import GraphQLError

from config import settings


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


async def enforce_rate_limit(
    context: Any,
    operation: str,
    identity: str,
    policy: str,
) -> None:
    count_limit, period = _parse_policy(policy)
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = f"rate-limit:{operation}:{identity_hash}"
    count, ttl = await redis_client.eval(_INCREMENT_WITH_TTL, 1, key, period)
    if int(count) <= count_limit:
        return

    retry_after = max(int(ttl), 1)
    context.response.headers["Retry-After"] = str(retry_after)
    raise GraphQLError(
        "Rate limit exceeded",
        extensions={"code": "RATE_LIMITED", "retryAfter": retry_after},
    )


def _parse_policy(policy: str) -> tuple[int, int]:
    try:
        count_text, period_text = policy.split("/", maxsplit=1)
        count = int(count_text)
        unit = period_text.rstrip("s").lower()
        seconds = _PERIOD_SECONDS[unit]
    except (ValueError, KeyError) as error:
        raise ValueError(f"Invalid rate-limit policy: {policy!r}") from error
    if count <= 0:
        raise ValueError(f"Invalid rate-limit count: {policy!r}")
    return count, seconds
