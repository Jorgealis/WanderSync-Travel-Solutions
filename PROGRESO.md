# WanderSync Travel Solutions — Plan de Desarrollo y Progreso

> Parcial 2 · Patrones Arquitectónicos Avanzados · Duración: 2 semanas
> Tecnologías obligatorias: **Docker Compose · GraphQL · Patrón SAGA · Dask · Prefect**

**Leyenda de estado:** `[ ]` pendiente · `[~]` en curso · `[x]` terminado
**Roles:**
- **Rol A — Backend transaccional y seguridad:** microservicios de dominio, SAGA, API Gateway GraphQL, autenticación, rate limiting.
- **Rol B — Datos, infraestructura y frontend:** Docker Compose, Postgres/Hasura, scraping, Dask, Prefect, frontend, auditoría de dependencias.
- **A+B:** tarea conjunta (contratos, integración, demo).

---

## 1. Stack tecnológico propuesto

La idea es usar **Python en todo el backend**, porque Dask y Prefect son nativos de Python. Así los dos roles comparten librerías, modelos y herramientas (Pydantic, SQLAlchemy, pytest, pip-audit).

| Capa | Tecnología | Por qué |
|---|---|---|
| Orquestación de contenedores | **Docker + Docker Compose v2** (perfiles, `healthcheck`, `depends_on: condition: service_healthy`) | Requisito obligatorio; el sistema arranca con un solo `docker compose up` |
| Microservicios (Vuelos, Hoteles, Autos, Órdenes/Facturación, Auth) | **Python 3.12 + FastAPI + SQLAlchemy 2 (async) + Alembic + Pydantic v2** | Rápido de desarrollar, asíncrono y con OpenAPI incluido para probar los servicios internos |
| API Gateway | **FastAPI + Strawberry GraphQL** | Único punto de entrada del frontend. Resolvers con DataLoader (evita N+1) y paso de los campos seleccionados (evita over-fetching) |
| Base de datos | **PostgreSQL 16**: un esquema por servicio (`flights`, `hotels`, `cars`, `orders`, `auth`) y un usuario de BD por servicio con privilegios solo sobre su esquema | Aislamiento de datos por servicio (*database-per-service* lógico) sin multiplicar contenedores |
| Capa GraphQL sobre la persistencia | **Hasura GraphQL Engine v2** sobre Postgres, con el catálogo en modo solo lectura | Cumple el requisito de "integración transparente con GraphQL" (equivale a Supabase/pg_graphql) y su consola sirve para la demo. *Alternativa:* imagen `supabase/postgres` con `pg_graphql` |
| SAGA | **SAGA orquestada** dentro de `orders-service`: máquina de estados persistida (`saga_instances`, `saga_steps`), llamadas HTTP internas con `httpx`, idempotencia por `saga_id` y reintentos con `tenacity` | La orquestación se diagrama, se depura y se demuestra con más facilidad que la coreografía. El estado persistido permite reanudar la SAGA si el orquestador se cae |
| Sesiones y rate limiting | **Redis 7.4** (sesiones del lado del servidor y contadores) + **slowapi/limits** | Permite regenerar el ID de sesión (contra Session Fixation) y aplicar rate limiting distribuido |
| Hashing de contraseñas | **argon2-cffi (Argon2id)** con `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4` | Requisito de seguridad |
| Fuentes de datos | **Fuentes públicas reales**, evaluadas una por una (ver §1.4): scraping de HTML (Google Flights) y API oficial (Hotelbeds). Sin datos simulados ni Faker | Requisito 3.1 del enunciado: capturar información real y actualizada de plataformas públicas |
| Scraping y parseo | **httpx + selectolax** (HTML renderizado en el servidor) y **pandas / dask.dataframe** para limpieza. *Playwright solo si una fuente lo exige y no implica saltarse protecciones* | Liviano y fácil de paralelizar en los workers de Dask |
| Computación distribuida | **Dask Distributed**: 1 `dask-scheduler` y N `dask-worker` (escalables con `--scale`) y dashboard en `:8787` | Requisito obligatorio |
| Orquestación y observabilidad | **Prefect 3**: `prefect-server` con UI en `:4200`, `prefect-worker` y **prefect-dask** (`DaskTaskRunner` apuntando al scheduler externo) | Requisito obligatorio: retries, schedules y monitoreo visual |
| Frontend | **React 18 + Vite + TypeScript + Apollo Client + GraphQL Codegen + TailwindCSS**, servido con **Nginx** | Las consultas tipadas y los fragments piden solo los campos necesarios |
| Pruebas | **pytest + pytest-asyncio + httpx**, **Vitest** en el frontend y un script E2E de la SAGA | Evidencia de *happy path* y de compensación |
| Supply chain | **pip-audit**, **npm audit**, **Trivy** (imágenes) y **Dependabot**/GitHub Actions (opcional) | Evidencia formal de la auditoría |
| Documentación | **Mermaid** (arquitectura y secuencias SAGA) en Markdown, exportado a PDF | Diagramas versionados en el repositorio |

### 1.1 Arquitectura general

```
                    ┌──────────────┐
  Navegador ───────▶│  frontend    │ (Nginx :3000)
                    └──────┬───────┘
                           │  GraphQL (única vía)
                    ┌──────▼───────┐      ┌─────────┐
                    │ api-gateway  │◀────▶│  Redis  │ sesiones + rate limit
                    │ (Strawberry) │      └─────────┘
                    └┬───┬───┬───┬─┘
         consultas   │   │   │   │ mutaciones
       de catálogo   │   │   │   └──────────────▶ auth-service
  ┌──────────────────▼┐  │   └──────────────────▶ orders-service (orquestador SAGA)
  │ Hasura (GraphQL   │  │                          │  │  │  │
  │ sobre Postgres)   │  │                          ▼  ▼  ▼  ▼
  └─────────┬─────────┘  │            flights-svc hotels-svc cars-svc payment (orders)
            │            │                 │          │        │
            ▼            ▼                 ▼          ▼        ▼
      ┌──────────────────────────────────────────────────────────┐
      │ PostgreSQL 16 (esquemas flights | hotels | cars | orders | auth) │
      └──────────────────────────────────────────────────────────┘
            ▲
            │ upsert masivo
  ┌─────────┴──────────┐   ┌────────────────┐   ┌─────────────────┐
  │ Dask scheduler +   │◀──│ Prefect worker │──▶│ Prefect server  │ (UI :4200)
  │ N dask-workers     │   │ (flow ingesta) │   └─────────────────┘
  └─────────┬──────────┘   └────────────────┘
            │ scraping HTTP (con pausas y límite de peticiones)
     ┌──────▼──────────────────────────────┐
     │ Fuentes públicas reales (Internet)  │
     │ Google Flights · hoteles · autos    │
     └─────────────────────────────────────┘
```

### 1.2 Estructura del repositorio

```
wandersync/
├── docker-compose.yml
├── .env.example
├── Makefile                      # atajos: up, down, seed, test, audit, demo-fail
├── services/
│   ├── api-gateway/              # Strawberry GraphQL
│   ├── auth-service/
│   ├── flights-service/
│   ├── hotels-service/
│   ├── cars-service/
│   └── orders-service/           # órdenes, facturación, pagos simulados, orquestador SAGA
├── data-pipeline/
│   ├── flows/                    # flows Prefect
│   ├── scrapers/                 # un scraper por fuente real (google_flights.py, ...)
│   ├── tests/fixtures/           # HTML real guardado para probar los parsers sin red
│   └── Dockerfile                # imagen común para dask-worker y prefect-worker
├── infra/
│   ├── postgres/init/            # creación de esquemas, roles y extensiones
│   └── hasura/metadata/          # metadata versionada (tablas, permisos)
├── frontend/
├── libs/common/                  # modelos y utilidades compartidas (logging, idempotencia)
├── tests/e2e/
└── docs/
    ├── arquitectura.md
    ├── saga.md
    ├── seguridad/                # reportes pip-audit, npm audit, trivy
    └── demo-guion.md
```

### 1.3 Puertos expuestos

| Servicio | Puerto host |
|---|---|
| frontend | 3000 |
| api-gateway (`/graphql`) | 8000 |
| Hasura console | 8080 |
| Prefect UI | 4200 |
| Dask dashboard | 8787 |
| Postgres | 5432 (solo en desarrollo) |
| Servicios internos | sin publicar; solo red interna `backend` |

### 1.4 Fuentes de datos: scraping real

**Política de scraping responsable** (aplica a todas las fuentes y se documenta en el informe técnico):
1. Solo se usan rutas que el `robots.txt` de la fuente **no prohíbe**.
2. **No se saltan CAPTCHAs ni protecciones anti-bot.** Si una fuente responde con un desafío, se descarta.
3. Se hacen pocas peticiones y espaciadas: pausa mínima entre peticiones a una misma fuente, límite de peticiones por ejecución y concurrencia limitada por fuente en Prefect, **aunque Dask tenga más workers libres**.
4. Si una fuente bloquea o cambia su HTML, el flow falla de forma controlada y el catálogo conserva los últimos datos válidos.

**Registro de fuentes.** Se evalúa una fuente a la vez: primero `robots.txt`, después una única petición de prueba.

| Catálogo | Fuente | `robots.txt` | Respuesta a una petición | Veredicto | Fecha |
|---|---|---|---|---|---|
| Vuelos | **Google Flights** (`/travel/flights?q=...`) | Permitido (solo prohíbe `/travel/flights/search` y `/travel/flights/s/`) | `200`, 55 vuelos en el HTML (precio COP, aerolínea, aeropuertos, horarios, duración). Validada el 2026-10-09: 21/21 búsquedas, 569 vuelos ([detalle](docs/fuentes/google-flights.md)) | ✅ **Elegida** | 2026-10-03 |
| Vuelos/hoteles/autos | Kayak | **Prohíbe** `/flights/`, `/hotels/` y `/cars/` | — | ❌ Descartada | 2026-10-03 |
| Hoteles | Booking.com | Permite `searchresults` | `202` con desafío anti-bot, sin datos | ❌ Descartada | 2026-10-03 |
| Hoteles | Google Hotels (`/travel/hotels/{ciudad}`) | Permitido, pero **redirige a `/travel/search`, que está prohibido** | `200` con precios y estrellas en el HTML | ❌ Descartada por `robots.txt` (ruta final prohibida) | 2026-10-09 |
| Hoteles | Despegar | **Prohíbe** `/search/hotels/` y `/accommodations/results/*` | Página de ciudad: `403` con CAPTCHA | ❌ Descartada | 2026-10-09 |
| Hoteles | Hoteles.com | **Prohíbe** `/Hotel-Search` | — | ❌ Descartada | 2026-10-09 |
| Hoteles | Trivago | **Prohíbe** `/*/srl?` (resultados) | — | ❌ Descartada | 2026-10-09 |
| Hoteles | Hostelworld | **Prohíbe** `/search` | — | ❌ Descartada | 2026-10-09 |
| Hoteles | TripAdvisor | Permite la página de ciudad | `403` con CAPTCHA | ❌ Descartada | 2026-10-09 |
| Hoteles | Expedia | Sin respuesta | — | ❌ Descartada | 2026-10-09 |
| Hoteles | **Agoda** (`/search?city=...&checkIn=...&los=...`) | Permitido (no restringe `/search`) | `200` pero el HTML es una aplicación JavaScript sin datos; **en un navegador real muestra resultados con fecha y precios en COP, sin CAPTCHA** | ❌ Descartada por decisión del equipo: requiere un navegador automatizado (Playwright) | 2026-10-09 |
| Hoteles | Bing, Viajes Falabella, Airbnb | **Prohíben** `/hotels/search`, `/search/` y `/s/*/*` | — | ❌ Descartadas | 2026-10-09 |
| Hoteles | PriceTravel, Almundo, HotelsCombined | Sin respuesta | — | ❌ Descartadas | 2026-10-09 |
| Hoteles | Amadeus Self-Service (API) | — | Portal cerrado el 2026-07-17 | ❌ Descartada | 2026-10-09 |
| Hoteles | **Hotelbeds** — API oficial, entorno de evaluación (servidores idénticos a producción, 50 peticiones/día) | No aplica: API documentada con claves propias | `200`: destinos de Colombia con códigos IATA y **67 hoteles reales en Medellín** con estrellas, habitaciones, régimen, precio (EUR) y cupos ([detalle](docs/fuentes/hotelbeds.md)) | ✅ **Elegida** (API oficial, no scraping) | 2026-10-09 |
| Autos | APIs oficiales | — | Amadeus cerró en julio de 2026; Hotelbeds no ofrece autos; no se encontró otra con registro abierto | ❌ | 2026-10-09 |
| Autos | Rentalcars | **Prohíbe** `/search*` y `/SearchResults*` | — | ❌ Descartada | 2026-10-09 |
| Autos | Discover Cars | **Prohíbe** `*/search/*` y `*/search-result*` | — | ❌ Descartada | 2026-10-09 |
| Autos | Despegar (autos) | **Prohíbe** `/cars/shop/` | — | ❌ Descartada | 2026-10-09 |
| Autos | Economy Bookings | `403` al pedir `robots.txt` | — | ❌ Descartada | 2026-10-09 |
| Autos | Hertz, Avis, Europcar (Colombia) | Sin respuesta | — | ❌ Descartadas | 2026-10-09 |
| Autos | Rentcars | Permite la búsqueda (solo prohíbe reservas y cuenta) | `403` con desafío de Cloudflare | ❌ Descartada | 2026-10-09 |
| Autos | **Localiza** (Colombia) | Permite todo salvo el login; publica `sitemap` con 129 URLs | Páginas de agencia por ciudad: `200`, sin anti-bot, pero **sin vehículos ni precios**: solo el formulario de búsqueda. Las "ofertas" son promociones, no tarifas con fecha | ❌ Descartada: una búsqueda real desde un navegador (MDE, 16→19 oct) respondió *"Falla al cargar las informaciones"*; los resultados dependen de JavaScript (la URL no cambia) y la página reporta a **Akamai Bot Manager** (POST repetidos a una ruta ofuscada). No se reintentó | 2026-10-09 |

**Decisión para autos (2026-10-09).** Ninguna de las 10 fuentes de autos evaluadas es viable sin incumplir la política. El enunciado (sección 3.1) permite explícitamente *"servicios mockeados que simulen la complejidad de dichas fuentes"*, así que los autos usarán una **fuente simulada**, servida por HTTP e ingerida con el mismo pipeline (Dask + Prefect + reintentos). Así el proyecto combina tres tipos de fuente: **scraping de HTML** (vuelos), **API oficial** (hoteles) y **servicio simulado** (autos).

**Impacto en el modelo de datos.** Las fuentes reales no publican cupos (asientos, habitaciones ni autos disponibles). El **inventario inicial lo asigna WanderSync** al insertar una oferta nueva (valor configurable) y desde ese momento lo gestiona la SAGA. Además, los precios llegan en COP y se normalizan a USD.

---

## 2. Hitos de sincronización

Son los puntos donde un rol depende del otro. Conviene acordarlos con fecha.

| Hito | Contenido | Desbloquea |
|---|---|---|
| **H0 — Contratos (día 1–2)** | Modelo de datos, SDL GraphQL del gateway, contratos REST internos (reserve/cancel/confirm), `.env.example` | Trabajo en paralelo de A y B |
| **H1 — Infra base (día 3)** | `docker compose up` levanta Postgres, Redis, Hasura, Dask y Prefect con healthchecks | Servicios de A sobre la infraestructura real |
| **H2 — Catálogo poblado (día 7)** | El flow Prefect+Dask llena las tablas de catálogo **con datos reales** de las fuentes elegidas | Búsqueda en el gateway y en el frontend |
| **H3 — SAGA funcional (día 8)** | Mutación `bookPackage` con *happy path* y compensaciones | Checkout en el frontend |
| **H4 — Code freeze (día 12)** | Todo integrado, seguridad aplicada | Auditoría final, documentación y grabación de la demo |

---

## 3. Lista de tareas en orden de desarrollo

### Fase 0 — Fundaciones y contratos (Días 1–2) · *A+B*

> Entregables: [CONTRIBUTING.md](CONTRIBUTING.md), [.env.example](.env.example) y los contratos en [docs/contratos/](docs/contratos/). Estos contratos son la fuente de verdad y solo cambian con un PR aprobado por ambos roles.

- [x] **0.1 (A+B)** Crear el repositorio Git, la estructura de carpetas (§1.2), `.gitignore`, `.editorconfig`, la convención de commits y la estrategia de ramas (`main` + `feat/*`).
- [x] **0.2 (A+B)** Definir el **modelo de datos** por esquema:
  - `flights.flight_offers` (origen, destino, fecha, aerolínea, precio, asientos disponibles, fuente, `scraped_at`, clave única de deduplicación)
  - `hotels.room_offers` y `cars.car_offers` (campos análogos)
  - `flights|hotels|cars.reservations` (`id`, `offer_id`, `saga_id` UNIQUE, `status`: `RESERVED/CANCELLED/CONFIRMED`)
  - `orders.orders`, `orders.payments`, `orders.saga_instances`, `orders.saga_steps`
  - `auth.users`
- [x] **0.3 (A+B)** Escribir el **SDL GraphQL** del gateway como contrato. Queries: `searchFlights`, `searchHotels`, `searchCars`, `searchPackages(origin, destination, dates, budget)`, `order(id)`, `myOrders`, `me`. Mutations: `register`, `login`, `logout`, `bookPackage(input, simulateFailureAt)`.
- [x] **0.4 (A)** Definir los **contratos REST internos** de los servicios de dominio: `POST /reservations` (idempotente por `saga_id`), `POST /reservations/{saga_id}/cancel` (compensación idempotente) y `POST /reservations/{saga_id}/confirm`.
- [x] **0.5 (B)** Crear `.env.example` con todas las variables (credenciales por servicio, URLs internas, secretos) y documentar que `.env` nunca se versiona.

### Fase 1 — Infraestructura base (Días 2–3)

**Rol B**
- [x] **1.1** Escribir `docker-compose.yml` con `postgres`, `redis`, `hasura`, `dask-scheduler`, `dask-worker` (con réplicas), `prefect-server` y `prefect-worker`, todos con `healthcheck` y redes `frontend`/`backend`.
- [x] **1.2** Crear el script `infra/postgres/init/01-roles-and-schemas.sh`: esquemas, un usuario por servicio dueño de su esquema, los usuarios `ingest` y `hasura_ro` (este último de solo lectura) y las bases auxiliares de Hasura y Prefect. *Los `GRANT` por tabla y por columna para `ingest` y `hasura_ro` van en la primera migración Alembic de cada servicio de catálogo (2.13–2.15), porque las tablas aún no existen.*
- [x] **1.3** Crear la imagen `data-pipeline/Dockerfile` (Python 3.12, dask, distributed, prefect, prefect-dask, httpx, selectolax, pandas, sqlalchemy, psycopg) y usar **las mismas versiones** en scheduler, workers y prefect-worker. *Si las versiones no coinciden, Dask falla.*
- [x] **1.4** Verificar el hito **H1**: `docker compose up` deja todo *healthy* sin pasos manuales. ✅ Verificado el 2026-10-03: arranque limpio (`down -v` + `up`) en unos 90 s con los 14 contenedores *healthy*, y el flow de humo `flows/smoke.py` repartió sus tareas entre los 3 workers de Dask.

**Rol A**
- [x] **1.5** Crear la **plantilla base de microservicio** FastAPI: config con pydantic-settings, conexión async a la BD, Alembic, `/health`, logging JSON con `correlation_id`, Dockerfile multi-stage con usuario no-root.
- [x] **1.6** Crear `libs/common`: middleware de `correlation_id`, cliente httpx con timeouts y reintentos, y utilidades de idempotencia.
- [x] **1.7** Hacer que las migraciones de Alembic corran al arrancar cada servicio (entrypoint `alembic upgrade head`), sin intervención manual.

### Fase 2 — Ingesta distribuida y servicios de dominio (Días 3–7)

> **Cambio de alcance (2026-10-03):** se reemplazan las fuentes simuladas por **scraping real**, evaluando y construyendo **una fuente a la vez** (ver §1.4). Cada scraper se prueba solo antes de integrarlo en Dask y Prefect.

**Rol B — Scraping real, Dask y Prefect**
- [x] **2.1** Evaluar las fuentes del enunciado (Google Flights, Kayak, Booking) con `robots.txt` y una petición de prueba cada una. Resultado: Google Flights elegida para vuelos; Kayak y Booking descartadas (registro en §1.4).
- [x] **2.2** Ajustar los contratos al scraping real (además: `generate_env.py --sync` para actualizar un `.env` existente sin perder secretos; `INGEST_DAYS_AHEAD` pasó a `INGEST_DATE_OFFSETS=7,14,30` para acotar las peticiones):
  - [modelo-datos.md](docs/contratos/modelo-datos.md): `flight_number` opcional; nuevos campos `operated_by`, `stops`, `price_original` y `currency_original`; inventario inicial asignado por el sistema
  - [schema.graphql](docs/contratos/schema.graphql): `flightNumber` opcional y `stops`
  - [.env.example](.env.example) y `docker-compose.yml`: quitar `MOCK_*` (incluido `MOCK_PROVIDERS_URL` en `dask-worker` y `prefect-worker`) e `INGEST_MAX_PAGES`; bajar `INGEST_SCHEDULE_CRON` de cada 10 min a cada hora; agregar `SCRAPER_*` (pausa entre peticiones, máximo de peticiones por ejecución, User-Agent, tasa de fallos simulados para la demo, inventario inicial)
  - [CONTRIBUTING.md](CONTRIBUTING.md): cambiar el ámbito de commit `mock` por `scraper`
- [x] **2.3** **Fuente 1 — scraper de Google Flights** (`scrapers/google_flights.py` + `scrapers/base.py`). ✅ 2026-10-09: 27 pruebas sin red pasan; en vivo, BOG→MDE devolvió 50 vuelos reales. Pruebas: `docker build -f data-pipeline/Dockerfile --target test -t wandersync/data-pipeline:test . && docker run --rm wandersync/data-pipeline:test`.
  - descarga solo ida por ruta y fecha (agregar `one way` a la consulta), con pausa entre peticiones y límite por ejecución
  - enviar un User-Agent de navegador: con el de httpx por defecto, Google redirige a `/travel/flights/unsupported` y no entrega vuelos (comprobado el 2026-10-03)
  - extracción de aerolínea, operador, aeropuertos, salida, llegada, duración, escalas y precio
  - **detección de bloqueo**: si llega un CAPTCHA o desafío, se lanza un error específico, **sin reintentar contra la fuente**
  - guarda una página real en `tests/fixtures/` y prueba el parser sin red (pytest)
  - prueba manual: una ruta (BOG→MDE) impresa por consola
- [x] **2.4** Validar el scraper de Google Flights en varias rutas y fechas (`INGEST_ROUTES`) y documentar sus límites: formato, campos que faltan y cambios de idioma o moneda. ✅ 2026-10-09: 21/21 búsquedas, 569 vuelos, 0 descartes, 0 anomalías. Límites en [docs/fuentes/google-flights.md](docs/fuentes/google-flights.md); revalidar con `python -m tools.validate_google_flights`.
- [x] **2.5** **Fuente 2 — evaluar fuentes de hoteles** con el mismo procedimiento que 2.1 (candidata inicial: Google Hotels) y registrar el resultado en §1.4. ✅ 2026-10-09: 15 fuentes evaluadas; ninguna permite scraping con fechas sin incumplir la política. Elegida **Hotelbeds (API oficial)**. Contrato de hoteles ajustado a sus datos reales; ficha en [docs/fuentes/hotelbeds.md](docs/fuentes/hotelbeds.md).
- [x] **2.6** **Cliente de Hotelbeds** (`scrapers/hotelbeds.py` + `scrapers/quota.py`). ✅ 2026-10-09: en vivo, CTG devolvió 68 hoteles y 326 ofertas sin descartes; 24 pruebas nuevas sin red (51 en total). El contador de cuota vive en el volumen `ingest-state`, compartido por todos los workers. Detalle de la tarea: con el mismo nivel de pruebas que 2.3: firma de las peticiones, consulta por ciudad × fecha × estadía, una oferta por hotel + habitación + régimen (la tarifa más barata), `allotment` como inventario inicial, **contador de cuota diaria (50/día)** que se detiene antes de agotarla, y `INGEST_STAY_NIGHTS=3,5` (30 peticiones por ejecución diaria; ver plan de cuota en la ficha).
- [x] **2.7** **Fuente 3 — evaluar fuentes de alquiler de autos** y registrar el resultado en §1.4. *Es la más difícil: Google no tiene búsqueda de autos.* Si ninguna fuente es viable sin saltarse protecciones, se documenta y **se decide con el equipo** antes de seguir.
- [x] **2.8** **Fuente simulada de autos** (decisión de 2.7) y su cliente, con el mismo nivel de pruebas que 2.3. ✅ 2026-10-09: servicio `mock-car-rental` (RutaFácil), scraper con paginación y 4 formatos de precio, 10 pruebas nuevas (64 en el pipeline); en vivo, 3 páginas y 18 autos. Ficha en [docs/fuentes/rutafacil-simulada.md](docs/fuentes/rutafacil-simulada.md). Detalle:
  - servicio `mock-car-rental` en Docker Compose que sirve resultados por ciudad y fechas (`MDE`, `CTG`, `SMR`, `BOG`, `ADZ`), con **complejidad de fuente real**: paginación, formatos de precio y fecha variables, campos faltantes, duplicados, latencia y fallos 5xx/429 configurables
  - datos verosímiles: modelos y categorías de autos reales del mercado colombiano, pero **empresas arrendadoras ficticias** (no se atribuyen precios inventados a marcas reales) y `source = wandersync-mock-cars`, declarado como simulado en el documento técnico
  - cliente `scrapers/mock_car_rental.py` con el mismo `PoliteClient` y la misma clasificación de errores
- [ ] **2.9** **Limpieza y normalización** paralelizable con `dask.bag`/`dask.dataframe`:
  - conversión COP → USD (vuelos) y EUR → USD (hoteles), con tasa configurable o de una fuente pública
  - descarte de precios fuera de rango (en Hotelbeds apareció un hotel "desde 497.102 EUR")
  - fechas a ISO/UTC y deduplicación por `(source, external_id)`
  - validación con Pydantic; los registros inválidos se descartan y se cuentan
- [ ] **2.10** **Persistencia por lotes**: upsert `ON CONFLICT DO UPDATE` que **nunca** modifica el inventario; el inventario inicial se asigna solo al insertar una oferta nueva.
- [ ] **2.11** **Flow de Prefect** `ingest_travel_data`:
  - `DaskTaskRunner(address="tcp://dask-scheduler:8786")` con fan-out `.map()` por fuente × ruta × fecha
  - `@task(retries=3, retry_delay_seconds=exponential_backoff(10), retry_jitter_factor=0.5)` en extracción y escritura; **sin reintentos** ante bloqueo (CAPTCHA)
  - **límite de concurrencia por fuente** (tags de Prefect), para no saturar las fuentes reales
  - interruptor `SCRAPER_FAULT_RATE`, que simula fallos de red, para demostrar los *retries* en vivo
  - subflows `ingest_flights`, `ingest_hotels` e `ingest_cars`, y artefactos con el resumen (descargados, válidos, descartados, insertados, actualizados)
- [ ] **2.12** **Deployment de Prefect** con schedule configurable (`INGEST_SCHEDULE_CRON`, frecuencia moderada, por ejemplo cada hora) que se registre solo al arrancar el contenedor, y verificación del hito **H2**: flow visible en Prefect, tareas repartidas en Dask, reintentos visibles y tablas con datos reales.

**Rol A — Servicios de dominio**
- [x] **2.13** **flights-service**: leer ofertas, `POST /reservations` (descuenta asientos con `SELECT ... FOR UPDATE`, es idempotente por `saga_id` y falla con 409 si no hay cupo), `cancel` (restaura el cupo y es idempotente), `confirm`.
- [x] **2.14** **hotels-service**: igual que 2.13 para habitaciones.
- [x] **2.15** **cars-service**: igual que 2.13 para vehículos.
- [x] **2.16** Agregar un **mecanismo de inyección de fallos** en cada servicio (header `X-Simulate-Failure` o flag de la SAGA), activo solo con `ENABLE_FAULT_INJECTION=true`.
- [x] **2.17** Escribir pruebas unitarias de la reserva y la cancelación: idempotencia, falta de cupo y doble cancelación. ✅ 2026-10-09: lógica común en `libs/common/wandersync_common/reservations.py`; batería de contrato de 14 pruebas (`wandersync_common/testing/reservation_contract.py`) que corre en los 3 servicios contra la BD real, incluidas concurrencia sin sobreventa y tombstones (42/42). Ejecutar: `python scripts/run_service_tests.py`. Permisos por columna verificados: `ingest` no puede modificar el inventario.

### Fase 3 — Patrón SAGA y capa GraphQL de datos (Días 6–8)

**Rol A — Orquestador SAGA (25 % de la nota)**
- [ ] **3.1** **orders-service**: crear la orden con estado `PENDING` y la factura (`orders.invoices`) con el cálculo del total del paquete.
- [ ] **3.2** Implementar la **máquina de estados de la SAGA** persistida:
  - Pasos compensables: `RESERVE_FLIGHT → RESERVE_HOTEL → RESERVE_CAR`; pivote: `PROCESS_PAYMENT`; retriables: `CONFIRM_FLIGHT → CONFIRM_HOTEL → CONFIRM_CAR → ISSUE_INVOICE`
  - Compensaciones en orden inverso, incluido el paso que falló (detalle en [api-interna.md §4](docs/contratos/api-interna.md))
  - Estados: `STARTED, COMPENSATING, COMPLETED, COMPENSATED, FAILED`
  - Cada paso se registra en `saga_steps` (paso, estado, intento, error y timestamps)
- [ ] **3.3** Implementar el **pago simulado** (`payments`) con su compensación de reembolso; el pago puede fallar de forma configurable.
- [ ] **3.4** Configurar **reintentos con backoff** en los pasos (fallos transitorios) antes de compensar, y reintentar también las compensaciones hasta que se completen (deben ser idempotentes).
- [ ] **3.5** Hacer la SAGA **recuperable**: al arrancar, `orders-service` retoma las SAGAs en estado `STARTED/COMPENSATING`, para cubrir una caída del orquestador.
- [ ] **3.6** Escribir pruebas de integración de la SAGA: *happy path*; fallo en autos (se cancelan hotel y vuelo); fallo en pago (se cancelan auto, hotel y vuelo); fallo en hotel (se cancela vuelo). Validar que el inventario vuelve al valor original.
- [ ] **3.7** Verificar el hito **H3**: endpoint interno `POST /orders/book` funcional con `simulate_failure_at`.

**Rol B — Hasura y base del frontend**
- [ ] **3.8** Configurar Hasura: registrar las tablas de catálogo, crear las relaciones, definir el rol `gateway` de solo lectura con límite de filas, y exportar la metadata a `infra/hasura/metadata` para que se aplique automáticamente en `docker compose up` (imagen `cli-migrations`).
- [ ] **3.9** Desactivar la consola y la introspección de Hasura para clientes externos; Hasura solo debe ser accesible por la red `backend` y protegido con `HASURA_GRAPHQL_ADMIN_SECRET`.
- [ ] **3.10** Montar el esqueleto del frontend: Vite + React + TS + Tailwind, Apollo Client con `credentials: 'include'`, GraphQL Codegen sobre el SDL del contrato (0.3) y rutas (`/login`, `/search`, `/package`, `/checkout`, `/orders/:id`).
- [ ] **3.11** Crear el Dockerfile multi-stage del frontend (build con Node y servido con Nginx) y añadirlo a compose.

### Fase 4 — API Gateway GraphQL y autenticación (Días 7–10)

**Rol A**
- [ ] **4.1** Implementar el **gateway con Strawberry** sobre el SDL acordado.
  - Las queries de catálogo se resuelven contra Hasura, **reenviando solo los campos que pidió el cliente** (`info.selected_fields`), para no generar over-fetching aguas abajo.
  - `searchPackages` consolida vuelos, hoteles y autos en una sola respuesta, con combinación por presupuesto y fechas.
  - Se usan DataLoaders para evitar N+1.
- [ ] **4.2** Implementar `bookPackage` → `orders-service` y `order(id)` con el detalle de los pasos de la SAGA (para mostrarlo en el frontend).
- [ ] **4.3** **auth-service**: `register` y `login` con **Argon2id** (parámetros de §1), rehash si cambian los parámetros y mensajes de error genéricos (sin enumeración de usuarios).
- [ ] **4.4** **Sesiones en Redis** con mitigación de **Session Fixation**:
  - en el login exitoso se **destruye la sesión previa y se emite un ID nuevo** (`secrets.token_urlsafe(32)`)
  - cookie `HttpOnly`, `Secure` (configurable en desarrollo), `SameSite=Strict` y expiración absoluta e inactiva
  - `logout` invalida la sesión en el servidor
- [ ] **4.5** Agregar **autorización** en los resolvers: `bookPackage`, `myOrders` y `order` exigen sesión, y un usuario solo ve sus propias órdenes.
- [ ] **4.6** Aplicar **límites al gateway**: profundidad máxima de query, coste o complejidad, introspección desactivada en producción, CORS restringido al origen del frontend y protección CSRF (header personalizado más SameSite).

**Rol B**
- [ ] **4.7** Crear la vista de **login/registro** en el frontend.
- [ ] **4.8** Crear la vista de **búsqueda** y el **constructor de paquetes** (selección de vuelo, hotel y auto) usando fragments con solo los campos que se muestran.
- [ ] **4.9** Crear la vista de **checkout**, con un panel de demo para elegir *"Simular fallo en: ninguno / vuelo / hotel / auto / pago"*.
- [ ] **4.10** Crear la vista de **detalle de orden** con una línea de tiempo de los pasos de la SAGA (reservas y compensaciones), consultada por polling.
- [ ] **4.11** Mostrar un indicador de "última sincronización de tarifas" (lee `scraped_at` del catálogo).

### Fase 5 — Ciberseguridad y endurecimiento (Días 10–12)

**Rol A**
- [ ] **5.1** Configurar el **rate limiting** con un backend Redis:
  - por **operación GraphQL** (`login`, `register`, `bookPackage`), porque todo pasa por el endpoint único `/graphql` y limitar por ruta no basta
  - límites por IP y por usuario, por ejemplo `login: 5/min/IP`, `bookPackage: 3/min/usuario`
  - respuesta GraphQL con un error `RATE_LIMITED` y `Retry-After`
- [ ] **5.2** Agregar rate limiting también en el endpoint de pago de `orders-service` (defensa en profundidad).
- [ ] **5.3** Escribir pruebas de seguridad automatizadas: que el ID de sesión cambie tras el login (pre-login ≠ post-login), que el hash almacenado empiece por `$argon2id$` y que la petición 6 de login en un minuto reciba 429/`RATE_LIMITED`.
- [ ] **5.4** Añadir headers de seguridad en el gateway y en Nginx (CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).

**Rol B**
- [ ] **5.5** **Supply chain audit**: ejecutar `pip-audit -r requirements.txt` en cada servicio, `npm audit --audit-level=moderate` en el frontend y `trivy image` sobre cada imagen; guardar los reportes en `docs/seguridad/` (JSON y resumen en Markdown).
- [ ] **5.6** Corregir o actualizar las dependencias vulnerables y documentar el antes y el después. Fijar versiones (`pip-compile --generate-hashes` / `package-lock.json`).
- [ ] **5.7** Endurecer los contenedores: imágenes `slim`, usuario no-root, `read_only` donde sea posible, sin secretos en las imágenes y solo los puertos necesarios publicados. *Si se marca la red `backend` como `internal: true`, los workers de Dask necesitan una red adicional con salida a Internet; sin ella, el scraping real deja de funcionar.*
- [ ] **5.8** (Opcional, suma puntos) Workflow de GitHub Actions que ejecute pip-audit, npm audit y trivy en cada PR, más Dependabot.

### Fase 6 — Integración y pruebas end-to-end (Días 11–12) · *A+B*

- [ ] **6.1 (A+B)** Probar el arranque limpio con `docker compose down -v && docker compose up --build`: todo debe levantar sin intervención manual, con migraciones, metadata de Hasura, deployment de Prefect y una primera ingesta real.
- [ ] **6.2 (A)** Escribir el script E2E `tests/e2e/test_saga.py`, que contra el gateway haga login → búsqueda → `bookPackage` en el *happy path* y con fallo en cada paso, y verifique la orden y el inventario.
- [ ] **6.3 (B)** Escribir el script E2E de ingesta: lanzar el flow manualmente y verificar las filas nuevas, los reintentos registrados en Prefect y que el inventario de las ofertas existentes no cambie.
- [ ] **6.4 (B)** Probar el escalado: `docker compose up --scale dask-worker=4` y mostrar el reparto de tareas en el dashboard de Dask.
- [ ] **6.5 (A+B)** Corregir los bugs de integración y alcanzar el hito **H4 (code freeze)**.

### Fase 7 — Documentación y demostración (Días 12–14)

**Rol A**
- [ ] **7.1** Escribir `docs/saga.md` con los **diagramas de secuencia en Mermaid**: (1) *happy path*; (2) fallo en autos con compensación de hotel y vuelo; (3) fallo en pago con reembolso más todas las cancelaciones. Incluir la tabla de pasos y compensaciones y la justificación de usar orquestación en lugar de coreografía.
- [ ] **7.2** Documentar la seguridad: diseño de sesiones (Session Fixation), parámetros de Argon2id y tabla de límites del rate limiting con su evidencia (capturas o salidas de las pruebas de 5.3).

**Rol B**
- [ ] **7.3** Escribir `docs/arquitectura.md` con el diagrama de componentes y despliegue (Mermaid/C4), el flujo de ingesta Fuentes reales → Prefect → Dask → Postgres → Hasura → Gateway, la **política de scraping responsable y el registro de fuentes (§1.4)** con sus limitaciones (términos de uso, cambios de HTML), y la justificación técnica de cada elección del stack.
- [ ] **7.4** Escribir un `README.md` con requisitos, `cp .env.example .env`, `docker compose up`, URLs de cada panel y usuarios demo.
- [ ] **7.5** Compilar el **Documento Técnico** final (Markdown → PDF) que una 7.1, 7.2 y 7.3.

**A+B**
- [ ] **7.6** Escribir el **guion de la demo** (`docs/demo-guion.md`) cubriendo los cuatro puntos obligatorios:
  - (a) UI de Prefect: flow de scraping real en ejecución, reintentos (con `SCRAPER_FAULT_RATE`) y estados
  - (b) dashboard de Dask: workers procesando tareas en paralelo
  - (c) frontend consumiendo GraphQL, con la pestaña Network del navegador mostrando las queries a `/graphql`
  - (d) checkout con fallo simulado en autos → línea de tiempo con compensaciones e inventario restaurado
- [ ] **7.7** Grabar el video de la demo y hacer un ensayo de la sustentación.
- [ ] **7.8** Revisión final del repositorio: sin secretos, sin archivos basura y con un historial de commits limpio.

---

## 4. Resumen de carga por rol

| Fase | Rol A (Backend / SAGA / Seguridad) | Rol B (Datos / Infra / Frontend) |
|---|---|---|
| 0 | Contratos REST internos | `.env.example` (el resto, en conjunto) |
| 1 | Plantilla de microservicio, `libs/common` | Docker Compose, Postgres init, imagen de Dask/Prefect |
| 2 | Servicios de vuelos, hoteles y autos con inyección de fallos | Evaluación de fuentes reales, un scraper por fuente, limpieza, Dask, flow de Prefect |
| 3 | Orquestador SAGA, pagos y pruebas | Hasura, esqueleto del frontend |
| 4 | Gateway Strawberry, auth, sesiones | Vistas del frontend (búsqueda, checkout, línea de tiempo SAGA) |
| 5 | Rate limiting, pruebas de seguridad, headers | Supply chain audit, hardening de contenedores |
| 6 | E2E de la SAGA | E2E de ingesta, escalado de Dask |
| 7 | `saga.md`, documentación de seguridad | `arquitectura.md`, README, documento final |

---

## 5. Matriz de trazabilidad con la rúbrica

| Criterio (peso) | Requisito | Tareas que lo cubren |
|---|---|---|
| Arquitectura y Dockerización (15 %) | Microservicios Vuelos/Hoteles/Autos/Órdenes/Gateway; `docker compose up` sin pasos manuales | 1.1–1.7, 2.13–2.15, 3.1, 3.11, 5.7, 6.1 |
| GraphQL y persistencia (15 %) | Gateway GraphQL único, consultas consolidadas, mutaciones, sin over-fetching, BD con GraphQL | 0.3, 2.2, 2.10, 3.8–3.9, 4.1–4.2, 4.6, 4.8 |
| SAGA (25 %) | *Happy path* + compensaciones automáticas ante fallos simulados | 0.4, 2.13–2.17, 3.1–3.7, 4.9–4.10, 6.2, 7.1 |
| Dask + Prefect (25 %) | Workers Dask haciendo scraping real e ingesta, flow Prefect con retries y monitoreo en UI | 1.3, 2.1–2.12, 6.3–6.4 |
| Ciberseguridad (20 %) | Session Fixation, Argon2id, rate limiting en auth/pago/checkout, supply chain audit | 4.3–4.6, 5.1–5.8, 7.2 |
| Entregables | Repo, documento técnico, demo (a)(b)(c)(d) | 0.1, 7.1–7.8 |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Versiones distintas de Dask entre el cliente (Prefect) y los workers | Una sola imagen `data-pipeline` para scheduler, workers y prefect-worker (tarea 1.3) |
| Se agota la cuota de Hotelbeds (50 peticiones/día) | Ingesta de hoteles diaria con contador propio, que se detiene antes del límite; el catálogo conserva los hoteles del día anterior |
| Una fuente real bloquea las peticiones o cambia su HTML | Detección de bloqueo sin reintentos agresivos; el catálogo conserva los últimos datos válidos; pruebas del parser con HTML guardado (`tests/fixtures/`) para detectar el cambio |
| La fuente falla justo durante la demo | Ejecutar y validar una ingesta antes de la sustentación; el catálogo ya poblado permite seguir con la SAGA aunque la fuente no responda |
| No existe fuente real viable para algún catálogo (por ejemplo, autos) | Se documenta en §1.4 y se decide con el equipo (tarea 2.7) antes de invertir tiempo |
| Términos de uso de las fuentes | Respetar `robots.txt`, pocas peticiones y espaciadas, uso académico; se declara como limitación en el documento técnico |
| Dask satura una fuente al paralelizar | Límite de concurrencia por fuente en Prefect y pausa mínima entre peticiones (tarea 2.11) |
| `docker compose up` falla por orden de arranque | `healthcheck` + `depends_on: condition: service_healthy` y entrypoints que esperan a la BD |
| Rate limiting inefectivo por el endpoint GraphQL único | Limitar por nombre de operación o campo raíz de la mutación (tarea 5.1) |
| Compensaciones que fallan a medias | Compensaciones idempotentes y reintentadas, con estado persistido y reanudación (3.4–3.5) |
| Over-fetching entre el gateway y Hasura | Reenviar solo los campos seleccionados (4.1) y usar fragments en el frontend (4.8) |
