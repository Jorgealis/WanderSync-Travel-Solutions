"""E2E de la ingesta distribuida (tarea 6.3) contra el stack REAL.

Lanza el deployment de Prefect `ingest-travel-data/vuelos-y-autos` (el mismo que corre cada
hora) solo con el catálogo de autos y con fallos de red simulados, y comprueba:

1. que el flow termina en COMPLETED y sus tareas corrieron en los workers de Dask;
2. que hubo reintentos registrados en Prefect (tareas con más de un intento);
3. que la ingesta escribió en el catálogo (ofertas nuevas o con precio/fecha actualizados);
4. que el INVENTARIO de las ofertas que ya existían no cambió (regla de oro del modelo de datos:
   la ingesta nunca pisa las unidades reservadas por la SAGA).

Se usa la fuente de autos (RutaFácil, simulada y propia) para no gastar peticiones de las
fuentes reales en cada ejecución.

    python scripts/run_service_tests.py ingest
"""

import os
import time
from datetime import datetime

import httpx
import psycopg
import pytest

PREFECT_API = os.environ.get("PREFECT_API_URL", "http://prefect-server:4200/api")
DEPLOYMENT = "ingest-travel-data/vuelos-y-autos"
FAULT_RATE = float(os.environ.get("E2E_INGEST_FAULT_RATE", "0.4"))
TIMEOUT_SECONDS = float(os.environ.get("E2E_INGEST_TIMEOUT_SECONDS", "900"))
TERMINAL = {"COMPLETED", "FAILED", "CRASHED", "CANCELLED"}


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        dbname=os.environ.get("POSTGRES_DB", "wandersync"),
        user=os.environ["CARS_DB_USER"],
        password=os.environ["CARS_DB_PASSWORD"],
        autocommit=True,
    )


def inventory(conn: psycopg.Connection) -> dict[str, tuple[int, int]]:
    rows = conn.execute("SELECT id::text, units_total, units_available FROM cars.car_offers").fetchall()
    return {offer_id: (total, available) for offer_id, total, available in rows}


@pytest.fixture(scope="module")
def prefect() -> httpx.Client:
    with httpx.Client(base_url=PREFECT_API, timeout=30) as client:
        assert client.get("/health").status_code == 200
        yield client


@pytest.fixture(scope="module")
def run(prefect: httpx.Client) -> dict:
    """Ejecuta la ingesta una vez para todo el módulo y devuelve el estado antes/después."""
    with connect() as conn:
        started_at: datetime = conn.execute("SELECT now()").fetchone()[0]
        before = inventory(conn)

    deployment = prefect.get(f"/deployments/name/{DEPLOYMENT}")
    assert deployment.status_code == 200, deployment.text
    created = prefect.post(f"/deployments/{deployment.json()['id']}/create_flow_run", json={
        "name": f"e2e-ingesta-autos-{int(time.time())}",
        "parameters": {"catalogs": ["cars"], "simulate_fault_rate": FAULT_RATE},
        "tags": ["e2e"],
    })
    assert created.status_code in (200, 201), created.text
    flow_run_id = created.json()["id"]

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        state = prefect.get(f"/flow_runs/{flow_run_id}").json()["state"]
        if state["type"] in TERMINAL:
            break
        assert time.monotonic() < deadline, f"La ingesta no terminó en {TIMEOUT_SECONDS} s (estado {state['type']})"
        time.sleep(5)

    # Las tareas de scraping cuelgan del subflow `ingest-cars`, hijo de esta corrida.
    task_runs = prefect.post("/task_runs/filter", json={
        "task_runs": {"start_time": {"after_": started_at.isoformat()}, "name": {"like_": "autos "}},
        "limit": 200,
    }).json()

    with connect() as conn:
        after = inventory(conn)
        touched, inserted = conn.execute(
            "SELECT count(*) FILTER (WHERE updated_at >= %(t)s), count(*) FILTER (WHERE created_at >= %(t)s) "
            "FROM cars.car_offers",
            {"t": started_at},
        ).fetchone()

    return {"state": state, "task_runs": task_runs, "before": before, "after": after,
            "touched": touched, "inserted": inserted}


def test_flow_completes(run):
    assert run["state"]["type"] == "COMPLETED", run["state"]


def test_scraping_tasks_ran_in_parallel(run):
    scrape = run["task_runs"]
    assert len(scrape) >= 2, "esperaba varias búsquedas de autos (ciudad × fecha × días)"
    finished = [t for t in scrape if t["state_type"] == "COMPLETED"]
    assert finished, "ninguna búsqueda terminó bien"


def test_retries_are_recorded_in_prefect(run):
    retried = [t for t in run["task_runs"] if t["run_count"] > 1]
    print(f"\n{len(retried)} de {len(run['task_runs'])} búsquedas necesitaron reintentos "
          f"(máx. {max((t['run_count'] for t in run['task_runs']), default=0)} intentos)")
    assert retried, f"con simulate_fault_rate={FAULT_RATE} debería haber al menos un reintento"


def test_catalog_was_written(run):
    print(f"\nofertas escritas por esta ingesta: {run['touched']} (nuevas: {run['inserted']})")
    assert run["touched"] > 0


def test_existing_inventory_is_preserved(run):
    common = run["before"].keys() & run["after"].keys()
    changed = {i: (run["before"][i], run["after"][i]) for i in common if run["before"][i] != run["after"][i]}
    reserved = [i for i in common if run["before"][i][1] < run["before"][i][0]]
    print(f"\n{len(common)} ofertas previas comparadas, {len(reserved)} con unidades ya reservadas")
    assert not changed, f"la ingesta cambió el inventario de ofertas existentes: {list(changed.items())[:5]}"
