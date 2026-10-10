# syntax=docker/dockerfile:1
# RutaFácil (SIMULADO): fuente de autos de WanderSync. Contexto de build: raíz del repo.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY services/mock-car-rental/requirements.lock /tmp/requirements.lock
# Dependencias con hashes (tarea 5.6) con pip 26.2.1 (la de la base tiene vulnerabilidades);
# después se desinstala pip: no se usa en ejecución (tarea 5.7).
RUN pip install --upgrade pip==26.2.1 \
    && pip install --require-hashes -r /tmp/requirements.lock \
    && python -m pip uninstall --yes pip \
    && apt-get update && apt-get upgrade --yes && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY services/mock-car-rental/app /app/app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
