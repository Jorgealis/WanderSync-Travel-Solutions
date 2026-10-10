# syntax=docker/dockerfile:1
# Imagen común de Dask + Prefect. Contexto de build: raíz del repositorio.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pip 26.2.1: la versión de la imagen base (25.0.1) tiene vulnerabilidades conocidas (auditoría 5.5).
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --upgrade pip==26.2.1
ENV PATH="/opt/venv/bin:$PATH"

# Dependencias con hashes SHA-256 (tarea 5.6): si un paquete publicado cambia, el build falla.
COPY data-pipeline/requirements.lock /tmp/requirements.lock
RUN pip install --require-hashes -r /tmp/requirements.lock

# pip solo hace falta para construir: fuera del venv que se copia a la imagen final.
RUN pip uninstall --yes pip

FROM python:3.12-slim AS runtime
# Sin pip en la imagen final (tarea 5.7): no se usa en ejecución y arrastra dependencias propias
# (urllib3, msgpack...) que también habría que mantener al día. La etapa `test` lo reinstala.
# Además, parches de seguridad de Debian publicados después de la imagen base.
RUN python -m pip uninstall --yes pip \
    && apt-get update && apt-get upgrade --yes && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PREFECT_HOME=/home/app/.prefect \
    PREFECT_UI_STATIC_DIRECTORY=/home/app/.prefect/ui \
    DASK_TEMPORARY_DIRECTORY=/tmp/dask

# Prefect y Dask necesitan un HOME escribible para su estado local.
# /var/lib/wandersync: estado compartido de la ingesta (p. ej. cuota diaria de Hotelbeds).
# Al montar el volumen `ingest-state` por primera vez, Docker copia este directorio con su dueño.
RUN groupadd --system app && useradd --system --gid app --create-home app     && mkdir -p /var/lib/wandersync && chown app:app /var/lib/wandersync

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
RUN python -m ensurepip && python -m pip install --no-cache-dir -r /tmp/requirements-dev.txt
USER app
CMD ["pytest"]
