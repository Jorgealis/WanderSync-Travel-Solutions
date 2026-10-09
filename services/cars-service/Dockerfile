# syntax=docker/dockerfile:1
# Contexto de build: raíz del repositorio (ver docker-compose.yml).

# --- Etapa 1: dependencias en un virtualenv ----------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY services/cars-service/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY libs/common /tmp/libs/common
RUN pip install --no-deps /tmp/libs/common

# --- Etapa 2: imagen final, sin herramientas de build y sin root -------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY services/cars-service/ /app/

USER app
EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]

# --- Etapa de pruebas (no se usa en producción): python scripts/run_service_tests.py ---
FROM runtime AS test
USER root
COPY services/cars-service/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt
USER app
ENTRYPOINT []
CMD ["pytest"]
