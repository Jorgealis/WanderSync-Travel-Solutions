#!/bin/sh
# Aplica las migraciones del servicio y arranca la API.
# Postgres ya está "healthy" (depends_on en docker-compose.yml), así que no hace falta esperar.
set -eu

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
# --no-access-log: CorrelationIdMiddleware ya registra cada petición en JSON.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers
