# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pip 26.2.1: la versión de la imagen base (25.0.1) tiene vulnerabilidades conocidas (auditoría 5.5).
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --upgrade pip==26.2.1
ENV PATH="/opt/venv/bin:$PATH"

# Dependencias con hashes SHA-256 (tarea 5.6): si un paquete publicado cambia, el build falla.
COPY services/api-gateway/requirements.lock /tmp/requirements.lock
RUN pip install --require-hashes -r /tmp/requirements.lock

COPY libs/common /tmp/libs/common
RUN pip install --no-deps /tmp/libs/common

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
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY services/api-gateway/ /app/

USER app
EXPOSE 8000

# --proxy-headers: la IP del cliente viene en X-Forwarded-For desde el Nginx del frontend, que la
# reemplaza con $remote_addr (no se puede falsificar a través de él). El gateway no publica puertos.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
