# syntax=docker/dockerfile:1
# RutaFácil (SIMULADO): fuente de autos de WanderSync. Contexto de build: raíz del repo.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY services/mock-car-rental/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
    && groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY services/mock-car-rental/app /app/app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
