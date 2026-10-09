# syntax=docker/dockerfile:1
# Imagen común de Dask + Prefect. Contexto de build: raíz del repositorio.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY data-pipeline/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PREFECT_HOME=/home/app/.prefect \
    PREFECT_UI_STATIC_DIRECTORY=/home/app/.prefect/ui \
    DASK_TEMPORARY_DIRECTORY=/tmp/dask

# Prefect y Dask necesitan un HOME escribible para su estado local.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app data-pipeline/ /app/

USER app

# --- Etapa de pruebas (no se usa en producción) --------------------------------
#   docker build -f data-pipeline/Dockerfile --target test -t wandersync/data-pipeline:test .
#   docker run --rm wandersync/data-pipeline:test
FROM runtime AS test
USER root
COPY data-pipeline/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt
USER app
CMD ["pytest"]
