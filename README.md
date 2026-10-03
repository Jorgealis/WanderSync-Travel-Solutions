# WanderSync Travel Solutions

Plataforma de empaquetamiento turístico dinámico (vuelos + hotel + auto) construida con microservicios, API Gateway GraphQL, patrón SAGA, ingesta distribuida con Dask y orquestación con Prefect.

> Proyecto del Parcial 2 — Patrones Arquitectónicos Avanzados. El avance está en [PROGRESO.md](PROGRESO.md).

## Arranque rápido

```bash
cp .env.example .env
docker compose up --build
```

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
