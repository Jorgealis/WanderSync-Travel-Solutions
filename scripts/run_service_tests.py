"""Ejecuta las pruebas de los microservicios contra la base de datos REAL del stack.

    python scripts/run_service_tests.py                 # flights, hotels y cars
    python scripts/run_service_tests.py flights         # solo uno
    python scripts/run_service_tests.py pipeline        # scrapers + ingesta (incluye BD real)

Requisitos: `docker compose up -d` (Postgres en marcha) y un .env generado.
Construye la etapa `test` del Dockerfile de cada servicio y la ejecuta en la red
`wandersync-backend` con las credenciales de ESE servicio (las mismas que en producción).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ["flights", "hotels", "cars"]


def read_env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if " #" in value and not value.lstrip().startswith('"'):
                value = value.split(" #", 1)[0]
            env[key.strip()] = value.strip().strip('"')
    return env


def run_pipeline(env: dict[str, str]) -> int:
    image = "wandersync/data-pipeline:test"
    print("\n=== data-pipeline: build ===", flush=True)
    subprocess.run(["docker", "build", "-q", "-f", "data-pipeline/Dockerfile", "--target", "test", "-t", image, "."],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    test_env = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_DB": env.get("POSTGRES_DB", "wandersync"),
        "INGEST_DB_USER": env["INGEST_DB_USER"],
        "INGEST_DB_PASSWORD": env["INGEST_DB_PASSWORD"],
        # Solo para limpiar lo que crean las pruebas (ingest no puede borrar).
        "CLEANUP_DB_USER": env["FLIGHTS_DB_USER"],
        "CLEANUP_DB_PASSWORD": env["FLIGHTS_DB_PASSWORD"],
    }
    args = ["docker", "run", "--rm", "--network", "wandersync-backend"]
    for key, value in test_env.items():
        args += ["-e", f"{key}={value}"]
    print("=== data-pipeline: pytest ===", flush=True)
    return subprocess.run([*args, image, "pytest"], cwd=ROOT).returncode


def run(service: str, env: dict[str, str]) -> int:
    if service == "pipeline":
        return run_pipeline(env)
    image = f"wandersync/{service}-service:test"
    print(f"\n=== {service}-service: build ===", flush=True)
    subprocess.run(
        ["docker", "build", "-q", "-f", f"services/{service}-service/Dockerfile", "--target", "test", "-t", image, "."],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL,
    )
    prefix = service.upper()
    test_env = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_DB": env.get("POSTGRES_DB", "wandersync"),
        "DB_USER": env[f"{prefix}_DB_USER"],
        "DB_PASSWORD": env[f"{prefix}_DB_PASSWORD"],
        "INTERNAL_API_TOKEN": env["INTERNAL_API_TOKEN"],
        "ENABLE_FAULT_INJECTION": "true",
        "LOG_LEVEL": "WARNING",
    }
    args = ["docker", "run", "--rm", "--network", "wandersync-backend"]
    for key, value in test_env.items():
        args += ["-e", f"{key}={value}"]
    print(f"=== {service}-service: pytest ===", flush=True)
    return subprocess.run([*args, image, "pytest"], cwd=ROOT).returncode


def main() -> int:
    env = read_env()
    services = sys.argv[1:] or SERVICES
    results = {service: run(service, env) for service in services}
    print("\nResumen:", ", ".join(f"{s}={'OK' if code == 0 else 'FALLÓ'}" for s, code in results.items()))
    return 0 if all(code == 0 for code in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
