"""Flow de humo: verifica la integración Prefect → Dask (hito H1).

Ejecuta tareas en el clúster Dask externo y comprueba que se repartan entre
varios workers. Debe aparecer en la UI de Prefect (:4200) y en el dashboard
de Dask (:8787).

    docker compose exec prefect-worker python -m flows.smoke
"""

import os
import socket
import time

from prefect import flow, get_run_logger, task
from prefect_dask import DaskTaskRunner

DASK_SCHEDULER_ADDRESS = os.environ.get("DASK_SCHEDULER_ADDRESS", "tcp://dask-scheduler:8786")


@task
def where_am_i(n: int) -> str:
    time.sleep(0.5)  # simula trabajo para que Dask reparta entre workers
    return socket.gethostname()


@flow(name="smoke-dask-integration", task_runner=DaskTaskRunner(address=DASK_SCHEDULER_ADDRESS))
def smoke(tasks: int = 12) -> dict[str, int]:
    logger = get_run_logger()
    hosts = [future.result() for future in where_am_i.map(range(tasks))]
    distribution = {host: hosts.count(host) for host in sorted(set(hosts))}
    logger.info("Tareas por worker de Dask: %s", distribution)
    return distribution


if __name__ == "__main__":
    print(smoke())
