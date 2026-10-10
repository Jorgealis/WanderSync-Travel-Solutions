"""Flow de Prefect `ingest_travel_data` (tarea 2.11): orquesta la ingesta en el clúster Dask.

    ingest_travel_data(catalogs=["flights", "cars"])        ← deployment cada hora
    ingest_travel_data(catalogs=["hotels"])                 ← deployment diario (cuota Hotelbeds)
      ├─ fetch_fx_rates                     tasas del día (TRM + BCE)
      ├─ ingest_flights   (subflow)  scrape.map(ruta × fecha) → normalize (dask.bag) → persist
      ├─ ingest_hotels    (subflow)  scrape.map(ciudad × fecha × noches) → normalize → persist
      └─ ingest_cars      (subflow)  scrape.map(ciudad × fecha × días) → normalize → persist

Dónde corre cada cosa:
- las tareas se ejecutan en los workers de Dask (`DaskTaskRunner` contra el scheduler externo);
- la normalización, además, reparte los registros con `dask.bag` en el mismo clúster.

Resiliencia (política de PROGRESO.md §1.4):
- reintentos con backoff exponencial y jitter SOLO ante fallos transitorios (red, 5xx,
  timeout, fallo simulado con SCRAPER_FAULT_RATE). Un bloqueo (CAPTCHA, 429), un cambio
  de formato o la cuota agotada NO se reintentan;
- límites de ritmo GLOBALES de Prefect por fuente (`rate_limit`): por ejemplo, 1 petición
  cada 5 s a Google Flights entre TODOS los workers, aunque Dask tenga más hilos libres;
- una búsqueda fallida no tumba el resto: el resumen la reporta y el catálogo conserva
  los datos anteriores.

Ejecución manual:  python -m flows.ingest flights cars
"""

import os
import sys
from collections import Counter
from dataclasses import asdict, replace
from datetime import date, timedelta

import dask.bag as dask_bag
from prefect import flow, get_run_logger, task, unmapped
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from prefect.cache_policies import NO_CACHE
from prefect.client.orchestration import get_client
from prefect.concurrency.sync import rate_limit
from prefect.tasks import exponential_backoff
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_dask import DaskTaskRunner, get_dask_client

from ingestion.fx import FxRates, fetch_rates
from ingestion.normalize import NORMALIZERS, Defaults, split_results
from ingestion.persist import ingest_engine, upsert
from scrapers import google_flights, hotelbeds, mock_car_rental
from scrapers.base import PoliteClient, ScraperSettings, TransientSourceError
from scrapers.quota import DailyQuota

DASK_ADDRESS = os.environ.get("DASK_SCHEDULER_ADDRESS", "tcp://dask-scheduler:8786")
RETRIES = int(os.environ.get("INGEST_TASK_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("INGEST_TASK_RETRY_DELAY_SECONDS", "10"))

# Límites de ritmo globales por fuente: (nombre, peticiones por segundo).
RATE_LIMITS = {
    "google-flights": 1 / float(os.environ.get("SCRAPER_MIN_DELAY_SECONDS", "5")),
    "hotelbeds": 1 / float(os.environ.get("HOTELBEDS_MIN_DELAY_SECONDS", "1")),
    "mock-cars": 5.0,
}


def dask_runner() -> DaskTaskRunner:
    return DaskTaskRunner(address=DASK_ADDRESS)


def retry_only_transient(_task, _task_run, state) -> bool:
    """Prefect reintenta solo si el fallo fue transitorio (red, 5xx, timeout, fallo simulado)."""
    try:
        state.result()
    except TransientSourceError:
        return True
    except Exception:
        return False
    return False


RETRY_POLICY = {
    "cache_policy": NO_CACHE,
    "retries": RETRIES,
    "retry_delay_seconds": exponential_backoff(backoff_factor=RETRY_DELAY),
    "retry_jitter_factor": 0.5,
    "retry_condition_fn": retry_only_transient,
}


# --------------------------------------------------------------------------- configuración

def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def search_dates() -> list[date]:
    return [date.today() + timedelta(days=int(o)) for o in env_list("INGEST_DATE_OFFSETS", "7,14,30")]


def routes() -> list[tuple[str, str]]:
    return [tuple(r.split("-", 1)) for r in env_list("INGEST_ROUTES", "BOG-MDE")]


def destination_cities() -> list[str]:
    return sorted({destination for _origin, destination in routes()})


def stay_lengths() -> list[int]:
    return [int(n) for n in env_list("INGEST_STAY_NIGHTS", "3,5")]


def defaults() -> Defaults:
    return Defaults(
        seats=int(os.environ.get("INGEST_DEFAULT_SEATS", "30")),
        rooms=int(os.environ.get("INGEST_DEFAULT_ROOMS", "10")),
        cars=int(os.environ.get("INGEST_DEFAULT_CARS", "5")),
    )


def scraper_settings(simulate_fault_rate: float = 0.0, **overrides) -> ScraperSettings:
    """Configuración del scraper; el parámetro del flow puede subir la tasa de fallos simulados (demo)."""
    base = ScraperSettings.from_env()
    return replace(base, fault_rate=max(base.fault_rate, simulate_fault_rate), **overrides)


def ensure_rate_limits() -> None:
    """Crea o actualiza (idempotente) los límites globales de Prefect por fuente."""

    async def upsert_all() -> None:
        async with get_client() as client:
            for source, per_second in RATE_LIMITS.items():
                await client.upsert_global_concurrency_limit_by_name(
                    f"scraper-{source}", limit=1, slot_decay_per_second=per_second
                )

    run_coro_as_sync(upsert_all())


# --------------------------------------------------------------------------- tareas

@task(name="fetch-fx-rates", retries=2, retry_delay_seconds=5, cache_policy=NO_CACHE)
def fetch_fx_rates() -> FxRates:
    rates = fetch_rates()
    get_run_logger().info("Tasas: %s COP/USD, %s USD/EUR (%s, %s)", rates.cop_per_usd, rates.usd_per_eur, rates.source, rates.as_of)
    return rates


@task(name="scrape-google-flights", task_run_name="vuelos {origin}-{destination} {day}", tags=["source:google-flights"], **RETRY_POLICY)
def scrape_flights(origin: str, destination: str, day: date, simulate_fault_rate: float = 0.0) -> dict:
    rate_limit("scraper-google-flights")
    with PoliteClient(scraper_settings(simulate_fault_rate)) as client:
        page = google_flights.fetch(client, origin, destination, day)
    records, failures = google_flights.parse_with_report(page, origin, destination, day)
    return {"search": f"{origin}-{destination} {day}", "records": records, "failures": failures}


@task(name="fetch-hotelbeds", task_run_name="hoteles {city} {check_in} {nights}n", tags=["source:hotelbeds"], **RETRY_POLICY)
def scrape_hotels(city: str, check_in: date, nights: int, simulate_fault_rate: float = 0.0) -> dict:
    rate_limit("scraper-hotelbeds")
    settings = hotelbeds.HotelbedsSettings.from_env()
    quota = DailyQuota(settings.quota_dir, hotelbeds.SOURCE, settings.daily_budget)
    with hotelbeds.make_client(settings, scraper_settings(simulate_fault_rate)) as client:
        payload = hotelbeds.fetch(client, settings, quota, city, check_in, nights)
    records, failures = hotelbeds.parse_with_report(payload)
    return {"search": f"{city} {check_in} {nights}n", "records": records, "failures": failures}


@task(name="scrape-mock-cars", task_run_name="autos {city} {pickup} {days}d", tags=["source:mock-cars"], **RETRY_POLICY)
def scrape_cars(city: str, pickup: date, days: int, simulate_fault_rate: float = 0.0) -> dict:
    settings = scraper_settings(simulate_fault_rate, min_delay_seconds=0.2)  # fuente interna
    records, failures = [], []
    with PoliteClient(settings) as client:
        dropoff = pickup + timedelta(days=days)
        rate_limit("scraper-mock-cars")
        records, failures, _pages = mock_car_rental.fetch_all(client, mock_car_rental.base_url(), city, pickup, dropoff)
    return {"search": f"{city} {pickup} {days}d", "records": records, "failures": failures}


@task(name="normalize", task_run_name="normalizar {catalog} ({count} registros)", cache_policy=NO_CACHE)
def normalize(catalog: str, records: list, fx: FxRates, count: int) -> dict:
    """Normaliza en paralelo con dask.bag sobre el mismo clúster en el que corre la tarea."""
    if not records:
        return {"rows": [], "discarded": [], "filled": 0}
    with get_dask_client():
        partitions = max(1, min(12, len(records) // 50))
        results = dask_bag.from_sequence(records, npartitions=partitions).map(NORMALIZERS[catalog], fx, defaults()).compute()
    rows, discarded, filled = split_results(results)
    return {"rows": rows, "discarded": discarded, "filled": filled}


@task(name="persist", task_run_name="guardar {catalog} ({count} filas)", retries=2, retry_delay_seconds=5, cache_policy=NO_CACHE)
def persist(catalog: str, rows: list[dict], count: int) -> dict:
    engine = ingest_engine()
    try:
        result = upsert(engine, catalog, rows, batch_size=int(os.environ.get("INGEST_BATCH_SIZE", "500")))
    finally:
        engine.dispose()
    return asdict(result)


# --------------------------------------------------------------------------- subflows

def _collect(futures) -> tuple[list[dict], list[str]]:
    """Resultados de un .map(): las búsquedas fallidas no tumban a las demás."""
    ok, failed = [], []
    for future in futures:
        try:
            ok.append(future.result())
        except Exception as exc:  # el estado fallido queda registrado en Prefect
            failed.append(f"{type(exc).__name__}: {exc}")
    return ok, failed


def _finish(catalog: str, fx: FxRates, ok: list[dict], failed: list[str], skipped: int = 0) -> dict:
    logger = get_run_logger()
    records = [record for result in ok for record in result["records"]]
    parse_failures = [failure for result in ok for failure in result["failures"]]
    # .submit(): se ejecutan en los workers de Dask, no en el proceso del flow.
    normalized = normalize.submit(catalog, records, fx, len(records)).result()
    saved = persist.submit(catalog, normalized["rows"], len(normalized["rows"])).result()

    summary = {
        "catálogo": catalog,
        "búsquedas OK": len(ok),
        "búsquedas fallidas": len(failed),
        "omitidas por cuota": skipped,
        "registros extraídos": len(records),
        "descartados (parser)": len(parse_failures),
        "descartados (validación)": len(normalized["discarded"]),
        "campos completados": normalized["filled"],
        "insertados": saved["inserted"],
        "actualizados": saved["updated"],
        "tasas": f"{fx.cop_per_usd} COP/USD · {fx.usd_per_eur} USD/EUR ({fx.source})",
    }
    create_table_artifact(
        key=f"ingest-{catalog}-summary", table=[{"métrica": k, "valor": str(v)} for k, v in summary.items()],
        description=f"Resumen de la ingesta de {catalog}",
    )
    reasons = Counter(r.split(":")[0] for r in normalized["discarded"] + parse_failures)
    if failed or reasons:
        lines = [f"# Incidencias de la ingesta de {catalog}", "", "## Búsquedas fallidas (sin reintento o reintentos agotados)"]
        lines += [f"- {f}" for f in failed[:20]] or ["- ninguna"]
        lines += ["", "## Motivos de descarte", *[f"- {reason}: {n}" for reason, n in reasons.most_common(10)]]
        create_markdown_artifact(key=f"ingest-{catalog}-issues", markdown="\n".join(lines))
    logger.info("Resumen %s: %s", catalog, summary)
    if failed and not ok:
        raise RuntimeError(f"Todas las búsquedas de {catalog} fallaron: {failed[:3]}")
    return summary


@flow(name="ingest-flights", task_runner=dask_runner())
def ingest_flights(fx: FxRates, simulate_fault_rate: float = 0.0) -> dict:
    plan = [(origin, destination, day) for day in search_dates() for origin, destination in routes()]
    futures = scrape_flights.map([p[0] for p in plan], [p[1] for p in plan], [p[2] for p in plan],
                                 simulate_fault_rate=unmapped(simulate_fault_rate))
    return _finish("flights", fx, *_collect(futures))


@flow(name="ingest-hotels", task_runner=dask_runner())
def ingest_hotels(fx: FxRates, simulate_fault_rate: float = 0.0) -> dict:
    plan = [(city, day, nights) for day in search_dates() for nights in stay_lengths() for city in destination_cities()]
    settings = hotelbeds.HotelbedsSettings.from_env()
    remaining = DailyQuota(settings.quota_dir, hotelbeds.SOURCE, settings.daily_budget).remaining()
    skipped = max(0, len(plan) - remaining)
    if skipped:
        get_run_logger().warning("Cuota de Hotelbeds: quedan %s peticiones hoy; se omiten %s búsquedas", remaining, skipped)
        plan = plan[:remaining]
    futures = scrape_hotels.map([p[0] for p in plan], [p[1] for p in plan], [p[2] for p in plan],
                                simulate_fault_rate=unmapped(simulate_fault_rate))
    return _finish("hotels", fx, *_collect(futures), skipped=skipped)


@flow(name="ingest-cars", task_runner=dask_runner())
def ingest_cars(fx: FxRates, simulate_fault_rate: float = 0.0) -> dict:
    plan = [(city, day, days) for day in search_dates() for days in stay_lengths() for city in destination_cities()]
    futures = scrape_cars.map([p[0] for p in plan], [p[1] for p in plan], [p[2] for p in plan],
                              simulate_fault_rate=unmapped(simulate_fault_rate))
    return _finish("cars", fx, *_collect(futures))


SUBFLOWS = {"flights": ingest_flights, "hotels": ingest_hotels, "cars": ingest_cars}


@flow(name="ingest-travel-data", task_runner=dask_runner(), log_prints=True)
def ingest_travel_data(
    catalogs: list[str] = ["flights", "cars"],  # noqa: B006 (parámetro de Prefect)
    simulate_fault_rate: float = 0.0,
) -> dict:
    """`simulate_fault_rate` (0–1) simula fallos de red ANTES de enviar cada petición, para
    demostrar los reintentos en vivo sin cargar las fuentes reales."""
    unknown = set(catalogs) - set(SUBFLOWS)
    if unknown:
        raise ValueError(f"Catálogos desconocidos: {sorted(unknown)}")
    ensure_rate_limits()
    fx = fetch_fx_rates()
    results = {}
    for catalog in catalogs:
        try:
            results[catalog] = SUBFLOWS[catalog](fx, simulate_fault_rate)
        except Exception as exc:  # un catálogo caído no impide ingerir los demás
            get_run_logger().error("Falló la ingesta de %s: %s", catalog, exc)
            results[catalog] = {"error": str(exc)}
    if all("error" in r for r in results.values()):
        raise RuntimeError(f"Fallaron todos los catálogos: {results}")
    return results


if __name__ == "__main__":
    print(ingest_travel_data(sys.argv[1:] or ["flights", "cars"]))
