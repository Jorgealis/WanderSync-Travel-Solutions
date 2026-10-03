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

| Panel | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API GraphQL | http://localhost:8000/graphql |
| Hasura console | http://localhost:8080 |
| Prefect UI | http://localhost:4200 |
| Dask dashboard | http://localhost:8787 |

*(La aplicación aún está en construcción; ver fases en [PROGRESO.md](PROGRESO.md).)*

## Documentación

- Contratos entre servicios: [docs/contratos/](docs/contratos/)
  - [Modelo de datos](docs/contratos/modelo-datos.md)
  - [Esquema GraphQL público](docs/contratos/schema.graphql)
  - [API REST interna y definición de la SAGA](docs/contratos/api-interna.md)
- Cómo contribuir: [CONTRIBUTING.md](CONTRIBUTING.md)
