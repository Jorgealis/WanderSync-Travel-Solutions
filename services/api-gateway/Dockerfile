# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY services/api-gateway/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY libs/common /tmp/libs/common
RUN pip install --no-deps /tmp/libs/common

FROM python:3.12-slim AS runtime

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
