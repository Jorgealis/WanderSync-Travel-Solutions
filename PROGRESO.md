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
| Sesiones y rate limiting | **Redis 7** (sesiones del lado del servidor y contadores) + **slowapi/limits** | Permite regenerar el ID de sesión (contra Session Fixation) y aplicar rate limiting distribuido |
| Hashing de contraseñas | **argon2-cffi (Argon2id)** con `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4` | Requisito de seguridad |
| Fuentes de scraping | **`mock-providers`**: servicio FastAPI que sirve HTML con paginación, latencia aleatoria y errores 5xx/429 inyectables, que imitan a Kayak, Booking y Rentalcars. Opcional: una fuente real | Fuentes estables para la demo; los fallos inyectados demuestran los *retries* |
| Scraping y parseo | **httpx + selectolax/BeautifulSoup4** y **pandas / dask.dataframe** para limpieza | Liviano y fácil de paralelizar |
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
            │ scraping HTTP
     ┌──────▼─────────┐
     │ mock-providers │ (HTML con fallos inyectables)
     └────────────────┘
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
│   ├── orders-service/           # órdenes, facturación, pagos simulados, orquestador SAGA
│   └── mock-providers/           # fuentes de scraping simuladas
├── data-pipeline/
│   ├── flows/                    # flows Prefect
│   ├── scrapers/                 # parsers por fuente
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

---

## 2. Hitos de sincronización

Son los puntos donde un rol depende del otro. Conviene acordarlos con fecha.

| Hito | Contenido | Desbloquea |
|---|---|---|
| **H0 — Contratos (día 1–2)** | Modelo de datos, SDL GraphQL del gateway, contratos REST internos (reserve/cancel/confirm), `.env.example` | Trabajo en paralelo de A y B |
| **H1 — Infra base (día 3)** | `docker compose up` levanta Postgres, Redis, Hasura, Dask y Prefect con healthchecks | Servicios de A sobre la infraestructura real |
| **H2 — Catálogo poblado (día 6)** | El flow Prefect+Dask llena las tablas de catálogo | Búsqueda en el gateway y en el frontend |
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
- [ ] **1.1** Escribir `docker-compose.yml` con `postgres`, `redis`, `hasura`, `dask-scheduler`, `dask-worker` (con réplicas), `prefect-server` y `prefect-worker`, todos con `healthcheck` y redes `frontend`/`backend`.
- [ ] **1.2** Crear los scripts `infra/postgres/init/*.sql`: esquemas, un usuario por servicio con `GRANT` restringido, un usuario `ingest` con escritura en el catálogo y un usuario `hasura_ro` de solo lectura.
- [ ] **1.3** Crear la imagen `data-pipeline/Dockerfile` (Python 3.12, dask, distributed, prefect, prefect-dask, httpx, selectolax, pandas, sqlalchemy, psycopg) y usar **las mismas versiones** en scheduler, workers y prefect-worker. *Si las versiones no coinciden, Dask falla.*
- [ ] **1.4** Verificar el hito **H1**: `docker compose up` deja todo *healthy* sin pasos manuales.

**Rol A**
- [ ] **1.5** Crear la **plantilla base de microservicio** FastAPI: config con pydantic-settings, conexión async a la BD, Alembic, `/health`, logging JSON con `correlation_id`, Dockerfile multi-stage con usuario no-root.
- [ ] **1.6** Crear `libs/common`: middleware de `correlation_id`, cliente httpx con timeouts y reintentos, y utilidades de idempotencia.
- [ ] **1.7** Hacer que las migraciones de Alembic corran al arrancar cada servicio (entrypoint `alembic upgrade head`), sin intervención manual.

### Fase 2 — Ingesta distribuida y servicios de dominio (Días 3–6)

**Rol B — Scraping, Dask y Prefect**
- [ ] **2.1** Crear el servicio **`mock-providers`**: páginas HTML de vuelos, hoteles y autos con paginación, datos generados con Faker y semilla, latencia aleatoria y **fallos configurables** (`FAILURE_RATE`, respuestas 500/429/timeouts).
- [ ] **2.2** Escribir los **scrapers/parsers** por fuente (`scrapers/flights.py`, `hotels.py`, `cars.py`): HTML → registros crudos.
- [ ] **2.3** Escribir las funciones de **limpieza y normalización** (monedas, fechas ISO, deduplicación, validación con Pydantic), paralelizables con `dask.dataframe`/`dask.bag`.
- [ ] **2.4** Implementar la **persistencia por lotes**: `INSERT ... ON CONFLICT DO UPDATE` (upsert) en bloques, para no saturar la BD.
- [ ] **2.5** Escribir el **flow de Prefect** `ingest_travel_data`:
  - `@task(retries=3, retry_delay_seconds=exponential_backoff(10), retry_jitter_factor=0.5)` para extracción y escritura
  - `task_runner=DaskTaskRunner(address="tcp://dask-scheduler:8786")`
  - fan-out con `.map()` por fuente × página × ruta, y subflows `ingest_flights`, `ingest_hotels`, `ingest_cars`
  - artefactos de Prefect (`create_table_artifact`) con un resumen de registros insertados y descartados
- [ ] **2.6** Crear un **deployment de Prefect** con schedule (por ejemplo, cada 10 min) que se registre automáticamente al arrancar el contenedor (`prefect deploy` o `flow.serve()` en el entrypoint).
- [ ] **2.7** Verificar el hito **H2**: el flow aparece en la UI de Prefect, los workers aparecen activos en el dashboard de Dask, se observan reintentos ante los fallos inyectados y las tablas quedan pobladas.

**Rol A — Servicios de dominio**
- [ ] **2.8** **flights-service**: leer ofertas, `POST /reservations` (descuenta asientos con `SELECT ... FOR UPDATE`, es idempotente por `saga_id` y falla con 409 si no hay cupo), `cancel` (restaura el cupo y es idempotente), `confirm`.
- [ ] **2.9** **hotels-service**: igual que 2.8 para habitaciones.
- [ ] **2.10** **cars-service**: igual que 2.8 para vehículos.
- [ ] **2.11** Agregar un **mecanismo de inyección de fallos** en cada servicio (header `X-Simulate-Failure` o flag de la SAGA), activo solo con `ENABLE_FAULT_INJECTION=true`.
- [ ] **2.12** Escribir pruebas unitarias de la reserva y la cancelación: idempotencia, falta de cupo y doble cancelación.

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
- [ ] **5.7** Endurecer los contenedores: imágenes `slim`, usuario no-root, `read_only` donde sea posible, sin secretos en las imágenes y solo los puertos necesarios publicados.
- [ ] **5.8** (Opcional, suma puntos) Workflow de GitHub Actions que ejecute pip-audit, npm audit y trivy en cada PR, más Dependabot.

### Fase 6 — Integración y pruebas end-to-end (Días 11–12) · *A+B*

- [ ] **6.1 (A+B)** Probar el arranque limpio con `docker compose down -v && docker compose up --build`: todo debe levantar sin intervención manual, con migraciones, metadata de Hasura, deployment de Prefect y datos semilla.
- [ ] **6.2 (A)** Escribir el script E2E `tests/e2e/test_saga.py`, que contra el gateway haga login → búsqueda → `bookPackage` en el *happy path* y con fallo en cada paso, y verifique la orden y el inventario.
- [ ] **6.3 (B)** Escribir el script E2E de ingesta: lanzar el flow manualmente y verificar las filas nuevas y los reintentos registrados en Prefect.
- [ ] **6.4 (B)** Probar el escalado: `docker compose up --scale dask-worker=4` y mostrar el reparto de tareas en el dashboard de Dask.
- [ ] **6.5 (A+B)** Corregir los bugs de integración y alcanzar el hito **H4 (code freeze)**.

### Fase 7 — Documentación y demostración (Días 12–14)

**Rol A**
- [ ] **7.1** Escribir `docs/saga.md` con los **diagramas de secuencia en Mermaid**: (1) *happy path*; (2) fallo en autos con compensación de hotel y vuelo; (3) fallo en pago con reembolso más todas las cancelaciones. Incluir la tabla de pasos y compensaciones y la justificación de usar orquestación en lugar de coreografía.
- [ ] **7.2** Documentar la seguridad: diseño de sesiones (Session Fixation), parámetros de Argon2id y tabla de límites del rate limiting con su evidencia (capturas o salidas de las pruebas de 5.3).

**Rol B**
- [ ] **7.3** Escribir `docs/arquitectura.md` con el diagrama de componentes y despliegue (Mermaid/C4), el flujo de ingesta Prefect → Dask → Postgres → Hasura → Gateway, y la justificación técnica de cada elección del stack.
- [ ] **7.4** Escribir un `README.md` con requisitos, `cp .env.example .env`, `docker compose up`, URLs de cada panel y usuarios demo.
- [ ] **7.5** Compilar el **Documento Técnico** final (Markdown → PDF) que una 7.1, 7.2 y 7.3.

**A+B**
- [ ] **7.6** Escribir el **guion de la demo** (`docs/demo-guion.md`) cubriendo los cuatro puntos obligatorios:
  - (a) UI de Prefect: flow en ejecución, reintentos y estados
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
| 2 | Servicios de vuelos, hoteles y autos con inyección de fallos | Mock providers, scrapers, Dask, flow de Prefect |
| 3 | Orquestador SAGA, pagos y pruebas | Hasura, esqueleto del frontend |
| 4 | Gateway Strawberry, auth, sesiones | Vistas del frontend (búsqueda, checkout, línea de tiempo SAGA) |
| 5 | Rate limiting, pruebas de seguridad, headers | Supply chain audit, hardening de contenedores |
| 6 | E2E de la SAGA | E2E de ingesta, escalado de Dask |
| 7 | `saga.md`, documentación de seguridad | `arquitectura.md`, README, documento final |

---

## 5. Matriz de trazabilidad con la rúbrica

| Criterio (peso) | Requisito | Tareas que lo cubren |
|---|---|---|
| Arquitectura y Dockerización (15 %) | Microservicios Vuelos/Hoteles/Autos/Órdenes/Gateway; `docker compose up` sin pasos manuales | 1.1–1.7, 2.8–2.10, 3.1, 3.11, 5.7, 6.1 |
| GraphQL y persistencia (15 %) | Gateway GraphQL único, consultas consolidadas, mutaciones, sin over-fetching, BD con GraphQL | 0.3, 2.4, 3.8–3.9, 4.1–4.2, 4.6, 4.8 |
| SAGA (25 %) | *Happy path* + compensaciones automáticas ante fallos simulados | 0.4, 2.8–2.12, 3.1–3.7, 4.9–4.10, 6.2, 7.1 |
| Dask + Prefect (25 %) | Workers Dask haciendo scraping e ingesta, flow Prefect con retries y monitoreo en UI | 1.3, 2.1–2.7, 6.3–6.4 |
| Ciberseguridad (20 %) | Session Fixation, Argon2id, rate limiting en auth/pago/checkout, supply chain audit | 4.3–4.6, 5.1–5.8, 7.2 |
| Entregables | Repo, documento técnico, demo (a)(b)(c)(d) | 0.1, 7.1–7.8 |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Versiones distintas de Dask entre el cliente (Prefect) y los workers | Una sola imagen `data-pipeline` para scheduler, workers y prefect-worker (tarea 1.3) |
| Scraping real bloqueado (CAPTCHA, cambios de HTML) | Usar `mock-providers` como fuente principal; una fuente real, si se usa, solo como complemento |
| `docker compose up` falla por orden de arranque | `healthcheck` + `depends_on: condition: service_healthy` y entrypoints que esperan a la BD |
| Rate limiting inefectivo por el endpoint GraphQL único | Limitar por nombre de operación o campo raíz de la mutación (tarea 5.1) |
| Compensaciones que fallan a medias | Compensaciones idempotentes y reintentadas, con estado persistido y reanudación (3.4–3.5) |
| Over-fetching entre el gateway y Hasura | Reenviar solo los campos seleccionados (4.1) y usar fragments en el frontend (4.8) |
