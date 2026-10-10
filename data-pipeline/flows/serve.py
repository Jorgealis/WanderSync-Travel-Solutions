"""Proceso de larga duración del contenedor `prefect-worker` (tarea 2.12).

Registra los deployments en el servidor de Prefect y ejecuta sus corridas programadas
(`prefect.serve`): no hace falta crear deployments a mano ni un work pool.

| Deployment                                   | Horario (America/Bogota)       | Catálogos       |
|----------------------------------------------|--------------------------------|-----------------|
| ingest-travel-data/vuelos-y-autos            | INGEST_SCHEDULE_CRON (cada hora) | flights, cars |
| ingest-travel-data/hoteles-diario            | INGEST_HOTELS_SCHEDULE_CRON (diario, cuota de Hotelbeds) | hotels |
| smoke-dask-integration/smoke                 | manual                         | —               |

Arranque en frío: si al iniciar algún catálogo está vacío (p. ej. tras `docker compose
down -v`), lanza una primera ingesta de inmediato, así el sistema queda con datos reales
sin pasos manuales.

Desde la UI de Prefect se puede ejecutar cualquier deployment con "Run" y cambiar sus
parámetros (por ejemplo `catalogs=["cars"]`).
"""

import logging
import os
import threading
import time

from prefect import serve
from prefect.deployments import run_deployment
from prefect.deployments.runner import EntrypointType
from prefect.schedules import Cron
from sqlalchemy import text

from flows.ingest import ingest_travel_data
from flows.smoke import smoke
from ingestion.persist import CATALOGS, ingest_engine

TIMEZONE = "America/Bogota"
# Los deployments se registran por RUTA DE MÓDULO ("flows.ingest:ingest_travel_data") y no por
# ruta de archivo: así las tareas se serializan como `flows.ingest.<tarea>`, que los workers de
# Dask pueden importar (misma imagen). Por ruta de archivo, Prefect carga el módulo con un nombre
# interno que los workers no conocen y Dask falla al deserializar el grafo de tareas.
BY_MODULE = {"entrypoint_type": EntrypointType.MODULE_PATH}
HOURLY = "vuelos-y-autos"
DAILY = "hoteles-diario"
log = logging.getLogger("wandersync.serve")


def deployments():
    hourly = ingest_travel_data.to_deployment(
        name=HOURLY,
        schedules=[Cron(os.environ.get("INGEST_SCHEDULE_CRON", "0 * * * *"), timezone=TIMEZONE)],
        parameters={"catalogs": ["flights", "cars"]},
        tags=["ingesta", "google-flights", "mock-cars"],
        description="Scraping real de Google Flights y fuente simulada de autos, cada hora.",
        **BY_MODULE,
    )
    daily = ingest_travel_data.to_deployment(
        name=DAILY,
        schedules=[Cron(os.environ.get("INGEST_HOTELS_SCHEDULE_CRON", "0 6 * * *"), timezone=TIMEZONE)],
        parameters={"catalogs": ["hotels"]},
        tags=["ingesta", "hotelbeds"],
        description="API de Hotelbeds una vez al día (cuota del entorno de evaluación: 50 peticiones/día).",
        **BY_MODULE,
    )
    smoke_check = smoke.to_deployment(
        name="smoke",
        tags=["diagnóstico"],
        description="Verifica que Prefect reparte tareas entre los workers de Dask.",
        **BY_MODULE,
    )
    return hourly, daily, smoke_check


def empty_catalogs() -> set[str]:
    engine = ingest_engine()
    try:
        with engine.connect() as conn:
            return {
                catalog for catalog, spec in CATALOGS.items()
                if conn.execute(text(f"SELECT NOT EXISTS (SELECT 1 FROM {spec.schema}.{spec.table})")).scalar()
            }
    finally:
        engine.dispose()


def bootstrap_first_ingestion() -> None:
    """Si hay catálogos vacíos, dispara la primera ingesta (cuando los deployments ya existen)."""
    for attempt in range(30):
        time.sleep(5)
        try:
            empty = empty_catalogs()
            triggered = []
            if empty & {"flights", "cars"}:
                run_deployment(f"ingest-travel-data/{HOURLY}", timeout=0, flow_run_name="primera-ingesta-vuelos-y-autos")
                triggered.append(HOURLY)
            if "hotels" in empty:
                run_deployment(f"ingest-travel-data/{DAILY}", timeout=0, flow_run_name="primera-ingesta-hoteles")
                triggered.append(DAILY)
            log.warning("Arranque: catálogos vacíos=%s → ingestas lanzadas=%s", sorted(empty) or "ninguno", triggered or "ninguna")
            return
        except Exception as exc:  # deployments aún no registrados o BD/migraciones aún no listas
            if attempt == 29:
                log.error("No se pudo comprobar el catálogo al arrancar: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    threading.Thread(target=bootstrap_first_ingestion, daemon=True).start()
    serve(*deployments())
