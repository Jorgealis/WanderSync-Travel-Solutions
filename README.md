# WanderSync Travel Solutions

Plataforma de empaquetamiento turístico dinámico (vuelo + hotel + auto) construida con
microservicios, API Gateway GraphQL, patrón SAGA, ingesta distribuida con Dask y orquestación con
Prefect.

> Parcial 2 — Patrones Arquitectónicos Avanzados. Plan y avance: [PROGRESO.md](PROGRESO.md).

| Tecnología obligatoria | Dónde |
|---|---|
| Docker Compose | `docker-compose.yml`: 17 contenedores con un solo `docker compose up` |
| GraphQL | `services/api-gateway` (Strawberry) + Hasura sobre Postgres |
| Patrón SAGA | `services/orders-service/app/saga.py` (orquestada, con compensaciones) — [docs/saga.md](docs/saga.md) |
| Dask | `dask-scheduler` + `dask-worker` ×3 ejecutan el scraping, la normalización y la ingesta |
| Prefect | `data-pipeline/flows/`: flows con reintentos, schedules y UI |

## Requisitos

- Docker Desktop (o Docker Engine) con Compose v2 y unos 6 GB de RAM libres.
- Python 3.10+ en el anfitrión (solo para los scripts de `scripts/`).
- Claves del entorno de evaluación de [Hotelbeds](https://developer.hotelbeds.com/) para el catálogo de
  hoteles (`HOTELBEDS_API_KEY` y `HOTELBEDS_API_SECRET` en `.env`). Sin ellas, vuelos y autos funcionan igual.

## Arranque

```bash
python scripts/generate_env.py   # crea .env desde .env.example con secretos aleatorios
docker compose up --build
```

El primer arranque construye las imágenes (varios minutos). Al quedar todo *healthy*:

- las migraciones de cada servicio y la metadata de Hasura ya están aplicadas;
- Prefect registró sus deployments y, si el catálogo está vacío, lanzó la **primera ingesta real**
  (vuelos y autos en unos minutos; hoteles según la cuota diaria de Hotelbeds).

Si un puerto está ocupado, cámbielo en `.env` (`FRONTEND_HOST_PORT`, `PREFECT_HOST_PORT` +
`PREFECT_UI_API_URL`, `DASK_DASHBOARD_HOST_PORT`). Tras un `git pull` que cambie `.env.example`:
`python scripts/generate_env.py --sync`. Para empezar de cero (borra los datos): `docker compose down -v`.

## Paneles

| Panel | URL |
|---|---|
| Aplicación (frontend) | http://localhost:3000 — cree una cuenta en *Crear cuenta* (contraseña de 10+ caracteres) |
| API GraphQL | http://localhost:3000/graphql (Nginx la reenvía al gateway) |
| Prefect UI | http://localhost:4200 |
| Dask dashboard | http://localhost:8787 |
| Consola de Hasura, Postgres, gateway directo | Solo con `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d` → :8080, :5432, :8000 |

## Uso rápido

- **Ingesta manual**: Prefect UI → *Deployments* → `ingest-travel-data/vuelos-y-autos` → *Run*.
  Para ver reintentos: *Custom run* con `catalogs=["cars"]` y `simulate_fault_rate=0.4`.
  Por consola: `docker compose exec prefect-worker python -m flows.ingest flights cars`.
- **SAGA con fallo**: en el checkout, *Panel de demo · Simular fallo en* → `Auto` → la página de la orden
  muestra las compensaciones en vivo. Requiere `ENABLE_FAULT_INJECTION=true` (valor del `.env` de desarrollo).
- **Escalar Dask**: `docker compose up -d --scale dask-worker=4`.

## Pruebas

Todas corren contra el stack levantado:

```bash
python scripts/run_service_tests.py pipeline flights hotels cars   # 75 + 3×14 pruebas
python scripts/run_service_tests.py security                       # 15 pruebas de seguridad
python scripts/run_service_tests.py ingest                         # E2E Prefect + Dask (≈5 min)
```

E2E de la SAGA (happy path y compensaciones a través del gateway): ver [tests/e2e/README.md](tests/e2e/README.md).

Auditoría de dependencias: `python scripts/security_audit.py despues` (requiere `docker compose build`).

## Documentación

| Documento | Contenido |
|---|---|
| [docs/arquitectura.md](docs/arquitectura.md) | Componentes, despliegue y redes, flujo de ingesta, fuentes, justificación del stack |
| [docs/saga.md](docs/saga.md) | Pasos, compensaciones y diagramas de secuencia de la SAGA |
| [docs/seguridad/README.md](docs/seguridad/README.md) | Sesiones, Argon2id, rate limiting, supply chain (antes/después), endurecimiento |
| [docs/requerimientos.md](docs/requerimientos.md) | Recorrido por cada requisito del enunciado: cómo se cumple y cómo demostrarlo |
| [docs/demo-guion.md](docs/demo-guion.md) | Guion de la demostración en vivo |
| [docs/contratos/](docs/contratos/) | Modelo de datos, esquema GraphQL público y API interna |
| [docs/fuentes/](docs/fuentes/) | Ficha de cada fuente de datos |
| [docs/documento-tecnico.pdf](docs/documento-tecnico.pdf) | Documento técnico compilado (arquitectura + SAGA + seguridad) |

Cómo contribuir: [CONTRIBUTING.md](CONTRIBUTING.md).
