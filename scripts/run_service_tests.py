"""Ejecuta las pruebas de los microservicios contra la base de datos REAL del stack.

    python scripts/run_service_tests.py                 # flights, hotels y cars
    python scripts/run_service_tests.py flights         # solo uno
    python scripts/run_service_tests.py pipeline        # scrapers + ingesta (incluye BD real)
    python scripts/run_service_tests.py security        # pruebas de seguridad contra el stack (5.3)
    python scripts/run_service_tests.py ingest          # E2E de la ingesta con Prefect + Dask (6.3)

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


def run_security(env: dict[str, str]) -> int:
    """Pruebas de seguridad (tests/security) desde un contenedor conectado a backend y frontend."""
    image = "wandersync/data-pipeline:test"  # trae pytest, httpx y psycopg
    print("\n=== security: build ===", flush=True)
    subprocess.run(["docker", "build", "-q", "-f", "data-pipeline/Dockerfile", "--target", "test", "-t", image, "."],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    test_env = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_DB": env.get("POSTGRES_DB", "wandersync"),
        "AUTH_DB_USER": env["AUTH_DB_USER"],
        "AUTH_DB_PASSWORD": env["AUTH_DB_PASSWORD"],
        "INTERNAL_API_TOKEN": env["INTERNAL_API_TOKEN"],
        "SESSION_COOKIE_NAME": env.get("SESSION_COOKIE_NAME", "ws_session"),
    }
    name = "wandersync-security-tests"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    args = ["docker", "create", "--name", name, "--network", "wandersync-backend",
            "-v", f"{(ROOT / 'tests' / 'security').as_posix()}:/security:ro", "-w", "/security"]
    for key, value in test_env.items():
        args += ["-e", f"{key}={value}"]
    subprocess.run([*args, image, "pytest", "-p", "no:cacheprovider", "-v", "/security"], check=True, stdout=subprocess.DEVNULL)
    try:
        subprocess.run(["docker", "network", "connect", "wandersync-frontend", name], check=True)
        print("=== security: pytest ===", flush=True)
        return subprocess.run(["docker", "start", "-a", name], cwd=ROOT).returncode
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def run_ingest(env: dict[str, str]) -> int:
    """E2E de la ingesta (tests/ingest): lanza el deployment real de Prefect y revisa la BD."""
    image = "wandersync/data-pipeline:test"  # trae pytest, httpx y psycopg
    print("\n=== ingest: build ===", flush=True)
    subprocess.run(["docker", "build", "-q", "-f", "data-pipeline/Dockerfile", "--target", "test", "-t", image, "."],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    test_env = {
        "POSTGRES_HOST": "postgres",
        "POSTGRES_DB": env.get("POSTGRES_DB", "wandersync"),
        "CARS_DB_USER": env["CARS_DB_USER"],
        "CARS_DB_PASSWORD": env["CARS_DB_PASSWORD"],
        "PREFECT_API_URL": "http://prefect-server:4200/api",
    }
    args = ["docker", "run", "--rm", "--network", "wandersync-backend",
            "-v", f"{(ROOT / 'tests' / 'ingest').as_posix()}:/ingest:ro", "-w", "/ingest"]
    for key, value in test_env.items():
        args += ["-e", f"{key}={value}"]
    print("=== ingest: pytest ===", flush=True)
    return subprocess.run([*args, image, "pytest", "-p", "no:cacheprovider", "-v", "-s", "/ingest"], cwd=ROOT).returncode


def run(service: str, env: dict[str, str]) -> int:
    if service == "security":
        return run_security(env)
    if service == "ingest":
        return run_ingest(env)
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
