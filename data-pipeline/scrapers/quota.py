"""Contador de cuota diaria compartido entre procesos y contenedores.

Hotelbeds permite 50 peticiones por día en su entorno de evaluación. Las peticiones
pueden salir de cualquier worker de Dask (contenedores distintos) y de varias
ejecuciones del flow, así que el contador vive en un volumen Docker compartido
(`ingest-state`) y se protege con un bloqueo de archivo (fcntl.flock).

Cada petición se reserva ANTES de enviarse: si falla, igual cuenta, porque la API
también la cuenta. El día se toma en UTC.
"""

import fcntl
import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from scrapers.base import RequestBudgetExceeded


class DailyQuotaExceeded(RequestBudgetExceeded):
    """Se alcanzó el presupuesto diario de peticiones de una fuente. No se reintenta."""


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


class DailyQuota:
    def __init__(
        self,
        directory: str | Path,
        source: str,
        daily_budget: int,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self.directory = Path(directory)
        self.source = source
        self.daily_budget = daily_budget
        self._today = today
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self) -> Path:
        return self.directory / f"{self.source}-{self._today().isoformat()}.json"

    def used(self) -> int:
        path = self._path()
        if not path.exists():
            return 0
        return json.loads(path.read_text(encoding="utf-8") or "{}").get("used", 0)

    def remaining(self) -> int:
        return max(0, self.daily_budget - self.used())

    def reserve(self) -> int:
        """Reserva una petición y devuelve cuántas van hoy. Lanza DailyQuotaExceeded si no quedan."""
        path = self._path()
        with open(self.directory / f"{self.source}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            used = json.loads(path.read_text(encoding="utf-8") or "{}").get("used", 0) if path.exists() else 0
            if used >= self.daily_budget:
                raise DailyQuotaExceeded(
                    f"Presupuesto diario de {self.source} agotado: {used}/{self.daily_budget} peticiones hoy (UTC)"
                )
            used += 1
            path.write_text(json.dumps({"used": used, "budget": self.daily_budget}), encoding="utf-8")
            return used
