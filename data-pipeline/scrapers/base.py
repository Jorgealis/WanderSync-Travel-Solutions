"""Infraestructura común de los scrapers: configuración, errores y cliente HTTP "educado".

Clasificación de errores (decide qué hace el flow de Prefect en la tarea 2.11):

| Error                  | Ejemplo                                   | ¿Reintentar? |
|------------------------|-------------------------------------------|--------------|
| TransientSourceError   | timeout, error de red, 5xx, fallo simulado | Sí           |
| SourceBlockedError     | CAPTCHA, 429, "navegador no compatible"    | **No**       |
| RequestBudgetExceeded  | se alcanzó SCRAPER_MAX_REQUESTS_PER_RUN    | No           |
| ParseError             | la fuente cambió su HTML                   | No           |

Nunca se reintenta contra una fuente que bloquea: insistir sería intentar saltarse
su protección, algo que la política del proyecto prohíbe.
"""

import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)


class ScraperError(Exception):
    """Error base de los scrapers."""


class TransientSourceError(ScraperError):
    """Fallo temporal (red, 5xx, fallo simulado): se puede reintentar."""


class SourceBlockedError(ScraperError):
    """La fuente bloqueó o rechazó al cliente: NO se reintenta."""


class RequestBudgetExceeded(ScraperError):
    """Se alcanzó el máximo de peticiones permitido en esta ejecución."""


class ParseError(ScraperError):
    """La respuesta no tiene la estructura esperada (probable cambio de HTML)."""


@dataclass(frozen=True)
class ScraperSettings:
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str = "es-CO,es;q=0.9"
    timeout_seconds: float = 20.0
    min_delay_seconds: float = 5.0
    max_requests_per_run: int = 40
    fault_rate: float = 0.0

    @classmethod
    def from_env(cls) -> "ScraperSettings":
        """Lee las variables SCRAPER_* (ver .env.example)."""
        env = os.environ
        return cls(
            user_agent=env.get("SCRAPER_USER_AGENT") or DEFAULT_USER_AGENT,
            accept_language=env.get("SCRAPER_ACCEPT_LANGUAGE") or cls.accept_language,
            timeout_seconds=float(env.get("SCRAPER_TIMEOUT_SECONDS", cls.timeout_seconds)),
            min_delay_seconds=float(env.get("SCRAPER_MIN_DELAY_SECONDS", cls.min_delay_seconds)),
            max_requests_per_run=int(
                env.get("SCRAPER_MAX_REQUESTS_PER_RUN", cls.max_requests_per_run)
            ),
            fault_rate=float(env.get("SCRAPER_FAULT_RATE", cls.fault_rate)),
        )


class PoliteClient:
    """Cliente HTTP que aplica la política de scraping responsable a UNA fuente.

    - espera al menos `min_delay_seconds` entre peticiones;
    - no supera `max_requests_per_run` peticiones;
    - con probabilidad `fault_rate` simula un fallo de red ANTES de enviar nada,
      para demostrar los reintentos de Prefect sin cargar la fuente real;
    - convierte las respuestas en los errores de la tabla del módulo.

    Cada instancia lleva su propia cuenta. Cuando varias tareas de Dask scrapean la
    misma fuente en paralelo, el límite global lo pone la concurrencia por fuente
    de Prefect (tarea 2.11).
    """

    def __init__(
        self,
        settings: ScraperSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings
        self.requests_made = 0
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_request_at: float | None = None
        self._client = httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": settings.accept_language,
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )

    def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        return self.request("GET", url, params=params)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self.requests_made >= self.settings.max_requests_per_run:
            raise RequestBudgetExceeded(
                f"Límite de {self.settings.max_requests_per_run} peticiones por ejecución alcanzado"
            )

        if self._rng.random() < self.settings.fault_rate:
            raise TransientSourceError("Fallo de red SIMULADO (SCRAPER_FAULT_RATE)")

        self._wait_turn()
        self.requests_made += 1
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.TransportError as exc:  # incluye timeouts
            raise TransientSourceError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            self._last_request_at = self._clock()

        self._raise_for_blocking(response)
        return response

    def _wait_turn(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.settings.min_delay_seconds - (self._clock() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    @staticmethod
    def _raise_for_blocking(response: httpx.Response) -> None:
        final = urlsplit(str(response.url))
        if final.netloc.startswith("consent.") or "/sorry/" in final.path:
            raise SourceBlockedError(f"La fuente pidió verificación (CAPTCHA/consentimiento): {final.netloc}{final.path}")
        if final.path.endswith("/unsupported"):
            raise SourceBlockedError(
                "La fuente marcó el cliente como navegador no compatible: revisar SCRAPER_USER_AGENT"
            )
        if response.status_code == 429:
            raise SourceBlockedError("HTTP 429: la fuente pide reducir el ritmo de peticiones o se agotó su cuota")
        if response.status_code in (401, 403) and "json" in response.headers.get("content-type", ""):
            raise SourceBlockedError(f"HTTP {response.status_code}: credenciales rechazadas por la API")
        if response.status_code >= 500:
            raise TransientSourceError(f"HTTP {response.status_code} de la fuente")
        if response.status_code >= 400:
            raise SourceBlockedError(f"HTTP {response.status_code} de la fuente")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
