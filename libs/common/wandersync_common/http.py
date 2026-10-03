"""Cliente HTTP para llamadas entre servicios.

Aplica la clasificación de errores del contrato (docs/contratos/api-interna.md §1):
- 5xx, timeout o error de conexión → transitorio → se reintenta;
- 4xx → fallo de negocio → no se reintenta.
"""

import uuid
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from wandersync_common.middleware import CORRELATION_HEADER, current_correlation_id
from wandersync_common.security import INTERNAL_TOKEN_HEADER


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):  # incluye timeouts y errores de conexión
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def transient_retrying(
    max_attempts: int, backoff_seconds: float, max_backoff_seconds: float = 30.0
) -> AsyncRetrying:
    """Política de reintentos con backoff exponencial + jitter, solo para fallos transitorios.

    Uso:
        async for attempt in transient_retrying(3, 0.5):
            with attempt:
                response = await client.request("POST", "/reservations", json=body)
                response.raise_for_status()
    """
    return AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff_seconds, max=max_backoff_seconds)
        + wait_random(0, backoff_seconds),
        retry=retry_if_exception(is_transient),
        reraise=True,
    )


class InternalClient:
    """httpx.AsyncClient que añade X-Internal-Token y propaga X-Correlation-ID."""

    def __init__(self, base_url: str, internal_token: str, timeout_seconds: float = 3.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers={INTERNAL_TOKEN_HEADER: internal_token},
        )

    async def request(
        self, method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
    ) -> httpx.Response:
        merged = {CORRELATION_HEADER: current_correlation_id() or str(uuid.uuid4())}
        merged.update(headers or {})
        return await self._client.request(method, url, headers=merged, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()
