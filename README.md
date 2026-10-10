# WanderSync Travel Solutions

Plataforma de empaquetamiento turístico dinámico (vuelos + hotel + auto) construida con microservicios, API Gateway GraphQL, patrón SAGA, ingesta distribuida con Dask y orquestación con Prefect.

> Proyecto del Parcial 2 — Patrones Arquitectónicos Avanzados. El avance está en [PROGRESO.md](PROGRESO.md).

## Arranque rápido

```bash
python scripts/generate_env.py   # crea .env con secretos aleatorios
docker compose up --build
```

El primer arranque tarda unos minutos (construye las imágenes); los siguientes, alrededor de 90 s hasta que todo está *healthy*. Para empezar de cero, incluida la base de datos: `docker compose down -v`.

Cuando cambie `.env.example` (por ejemplo, tras un `git pull`), actualice su `.env` sin perder los secretos con `python scripts/generate_env.py --sync`.

Si algún puerto ya está ocupado por otro proyecto, cámbielo en `.env` (`*_HOST_PORT`). Si cambia el de Prefect, ajuste también `PREFECT_UI_API_URL`.

## Frontend (React + Apollo)

```bash
# Desarrollo con recarga en caliente (requiere el gateway publicado):
docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d
cd frontend && npm ci && npm run dev     # http://localhost:5173
```

Los tipos de las consultas se generan desde el contrato [`docs/contratos/schema.graphql`](docs/contratos/schema.graphql) con `npm run codegen` (también lo hace `npm run build`).

## Ingesta de datos (Fase 2)

Tres fuentes, tres tipos de ingesta, un mismo pipeline (Prefect + Dask):

| Catálogo | Fuente | Tipo | Ficha |
|---|---|---|---|
| Vuelos | Google Flights | Scraping de HTML real | [docs/fuentes/google-flights.md](docs/fuentes/google-flights.md) |
| Hoteles | Hotelbeds (entorno de evaluación) | API oficial (requiere claves propias en `.env`) | [docs/fuentes/hotelbeds.md](docs/fuentes/hotelbeds.md) |
| Autos | RutaFácil | Servicio **simulado** (sección 3.1 del enunciado) | [docs/fuentes/rutafacil-simulada.md](docs/fuentes/rutafacil-simulada.md) |

Al arrancar con el catálogo vacío, `prefect-worker` lanza la primera ingesta automáticamente. Después: vuelos y autos cada hora, hoteles una vez al día.

```bash
# Ingesta manual de uno o varios catálogos
docker compose exec prefect-worker python -m flows.ingest flights cars
```

**Demo de reintentos:** en la UI de Prefect → Deployments → `ingest-travel-data/vuelos-y-autos` → *Run* → *Custom run* con `catalogs=["cars"]` y `simulate_fault_rate=0.3`.

```bash
# Pruebas (requieren el stack levantado): scrapers e ingesta, y contrato de reservas
python scripts/run_service_tests.py pipeline flights hotels cars
```

| Panel | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API GraphQL | http://localhost:3000/graphql (Nginx la reenvía al gateway, que no publica puertos; acceso directo en el 8000 con `docker-compose.debug.yml`) |
| Hasura console | http://localhost:8080 — solo con `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d` (por defecto Hasura no publica puertos) |
| Prefect UI | http://localhost:4200 |
| Dask dashboard | http://localhost:8787 |

*(La aplicación aún está en construcción; ver fases en [PROGRESO.md](PROGRESO.md).)*

## Documentación

- Contratos entre servicios: [docs/contratos/](docs/contratos/)
  - [Modelo de datos](docs/contratos/modelo-datos.md)
  - [Esquema GraphQL público](docs/contratos/schema.graphql)
  - [API REST interna y definición de la SAGA](docs/contratos/api-interna.md)
- Cómo contribuir: [CONTRIBUTING.md](CONTRIBUTING.md)
