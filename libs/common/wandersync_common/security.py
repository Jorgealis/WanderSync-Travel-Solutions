import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Header

from wandersync_common.config import ServiceSettings
from wandersync_common.errors import AppError

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def internal_token_dependency(settings: ServiceSettings) -> Callable[..., Awaitable[None]]:
    """Dependencia FastAPI que exige el secreto compartido INTERNAL_API_TOKEN.

    Defensa en profundidad: aunque alguien alcance la red interna de Docker,
    no puede invocar los servicios sin el token.
    """
    expected = settings.internal_api_token.get_secret_value().encode()

    async def verify_internal_token(
        x_internal_token: Annotated[str | None, Header()] = None,
    ) -> None:
        # compare_digest: comparación en tiempo constante (sin timing attacks).
        if x_internal_token is None or not hmac.compare_digest(
            x_internal_token.encode(), expected
        ):
            raise AppError(401, "UNAUTHORIZED", "Missing or invalid internal token")

    return verify_internal_token
