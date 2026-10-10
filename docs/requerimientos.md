# Recorrido de requerimientos — cómo se cumple cada uno y cómo demostrarlo

Este documento sigue el enunciado del Parcial 2 sección por sección. Para cada requisito indica:

- **Cómo se cumple**: la decisión de diseño.
- **Dónde está**: archivos y líneas para enseñar en la sustentación.
- **Cómo demostrarlo**: qué ejecutar o mostrar en vivo (los números de paso remiten a
  [demo-guion.md](demo-guion.md)).

Preparación común: stack levantado (`docker compose up -d`), navegador en `http://localhost:3000`,
Prefect en `http://localhost:4200` (o el puerto de `PREFECT_HOST_PORT`) y Dask en `http://localhost:8787`.

---

## §1. Tecnologías nucleares obligatorias

| Tecnología | Cómo se cumple | Dónde está | Cómo demostrarlo |
|---|---|---|---|
| **Docker Compose** | 17 contenedores, un `Dockerfile` por servicio, todo con `docker compose up` | [docker-compose.yml](../docker-compose.yml), `services/*/Dockerfile`, [data-pipeline/Dockerfile](../data-pipeline/Dockerfile), [frontend/Dockerfile](../frontend/Dockerfile) | `docker compose ps` → 17 servicios `healthy` (paso 1) |
| **GraphQL** | API Gateway Strawberry (única vía del frontend) + Hasura sobre Postgres | [services/api-gateway/schema.py](../services/api-gateway/schema.py), [docs/contratos/schema.graphql](contratos/schema.graphql) | Pestaña *Network* del navegador: todo va a `/graphql` (paso 3) |
| **Patrón SAGA** | SAGA orquestada en `orders-service` con compensaciones automáticas | [saga.py:71](../services/orders-service/app/saga.py#L71) (`execute_saga`), [saga.py:359](../services/orders-service/app/saga.py#L359) (`_compensate`) | Checkout con fallo simulado en *Auto* → línea de tiempo (paso 5) |
| **Dask** | Scheduler + 3 workers ejecutan scraping, normalización (`dask.bag`) e ingesta | [ingest.py:61](../data-pipeline/flows/ingest.py#L61) (`DaskTaskRunner`), [ingest.py:175](../data-pipeline/flows/ingest.py#L175) (`normalize`) | Dashboard de Dask → *Status* / *Workers* durante una ingesta (paso 2) |
| **Prefect** | Flow `ingest-travel-data` con retries, schedules, rate limits y artefactos | [ingest.py:279](../data-pipeline/flows/ingest.py#L279), [serve.py:46](../data-pipeline/flows/serve.py#L46) | UI de Prefect → *Runs* y *Deployments* (paso 2) |

---

## §3. Web scraping e ingesta distribuida

### 3.1 Fuentes de datos

**Cómo se cumple.** Tres fuentes y tres tipos de ingesta:

| Catálogo | Fuente | Tipo | Código |
|---|---|---|---|
| Vuelos | Google Flights | **Scraping real** de HTML | [scrapers/google_flights.py](../data-pipeline/scrapers/google_flights.py) |
| Hoteles | Hotelbeds | **API oficial** (entorno de evaluación, firma SHA-256) | [scrapers/hotelbeds.py](../data-pipeline/scrapers/hotelbeds.py) |
| Autos | RutaFácil | **Servicio simulado** (lo permite §3.1) con fallos 5xx, 429, lentitud y paginación | [services/mock-car-rental](../services/mock-car-rental), [scrapers/mock_car_rental.py](../data-pipeline/scrapers/mock_car_rental.py) |

Se evaluaron más de 25 fuentes con una política de scraping responsable: respeto de `robots.txt`,
nunca saltar CAPTCHAs y ritmo limitado. Registro en [PROGRESO.md §1.4](../PROGRESO.md#14-fuentes-de-datos-scraping-real)
y fichas en [docs/fuentes/](fuentes/).

**Cómo demostrarlo.**
- En el frontend, la búsqueda muestra *Última sincronización* y precios reales del día.
- En Prefect, la corrida de `vuelos-y-autos` muestra tareas `vuelos BOG-MDE …` con sus logs.
- Mostrar `docs/fuentes/google-flights.md` y explicar por qué Kayak y Booking se descartaron
  (`robots.txt` y anti-bot).

### 3.2 Procesamiento distribuido con Dask

**Cómo se cumple.**
- La recolección corre **fuera** de los servicios de la aplicación: en los workers de Dask, lanzada
  por Prefect. Los microservicios nunca hacen scraping.
- Cada búsqueda (ruta × fecha, ciudad × fecha × noches) es una **tarea independiente** en Dask
  (`scrape_flights.map(...)`).
- La **limpieza y estructuración** se reparten con `dask.bag.from_sequence(...).map(normalizer)`:
  conversión de COP/EUR a USD, validación y valores por defecto.

**Dónde está.**
- [ingest.py:144](../data-pipeline/flows/ingest.py#L144): tareas de scraping.
- [ingest.py:175](../data-pipeline/flows/ingest.py#L175): normalización con `dask.bag`.
- [ingestion/normalize.py](../data-pipeline/ingestion/normalize.py).
- `dask-scheduler` y `dask-worker` (con `replicas`) en [docker-compose.yml](../docker-compose.yml).

**Cómo demostrarlo.**
- Dashboard de Dask durante una ingesta: barras de tareas y *Task Stream* con varios workers en paralelo.
- `docker compose up -d --scale dask-worker=4` y `docker compose exec prefect-worker python -m flows.smoke`
  imprime el reparto, por ejemplo `{'4e86…': 4, '971b…': 2, 'b5fa…': 3, 'fcbc…': 3}`.
- Prueba automatizada: `python scripts/run_service_tests.py ingest`.

### 3.3 Persistencia con integración GraphQL

**Cómo se cumple.**
- Los workers escriben **directamente** en PostgreSQL 16 con un upsert por lotes, usando el usuario
  `ingest` con permisos mínimos.
- **Hasura** expone ese catálogo como GraphQL de forma transparente: es el equivalente a Supabase con
  pg_graphql que menciona el enunciado.
- El gateway consulta Hasura con el rol `gateway`, de solo lectura y con columnas permitidas.

**Dónde está.**
- [ingestion/persist.py](../data-pipeline/ingestion/persist.py): upsert y regla del inventario.
- [infra/hasura/metadata/databases/databases.yaml](../infra/hasura/metadata/databases/databases.yaml):
  tablas y permisos versionados.
- `_selection_names` en [schema.py:288](../services/api-gateway/schema.py#L288).

**Cómo demostrarlo.**
- Con `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d`, abrir la consola de
  Hasura en `http://localhost:8080` y ejecutar una query sobre `flight_offers`.
- Explicar que, por defecto, Hasura no publica puertos (seguridad).

---

## §4. Requisitos arquitectónicos obligatorios

### 4.1 Dockerización y microservicios

**Cómo se cumple.**
- Microservicios: **Vuelos**, **Hoteles**, **Autos**, **Órdenes/Facturación** (con pagos y el
  orquestador SAGA), **Gateway**, además de **Auth** y la fuente simulada.
- Cada servicio tiene su propio Dockerfile *multi-stage*, su esquema de BD y su usuario de BD con
  privilegios solo sobre ese esquema.
- Arranque con **un solo comando**: *healthchecks* y `depends_on: service_healthy`. Las migraciones
  (Alembic), la metadata de Hasura, los deployments de Prefect y la primera ingesta se aplican solos.

**Dónde está.**
- [docker-compose.yml](../docker-compose.yml).
- [services/](../services).
- `entrypoint.sh` de cada servicio: `alembic upgrade head`.
- [infra/postgres/init](../infra/postgres/init): esquemas y roles.
- [serve.py:84](../data-pipeline/flows/serve.py#L84): primera ingesta automática.

**Cómo demostrarlo.**
- `docker compose up -d` y luego `docker compose ps`: todo `healthy`.
- Mostrar el árbol de `services/` y un Dockerfile: etapas `builder`, `runtime` y `test`, usuario no-root.

### 4.2 GraphQL como API Gateway unificado

**Cómo se cumple.**
- **Exclusividad.** Nginx sirve el frontend y reenvía solo `/graphql` al gateway. Los microservicios
  están en la red interna `backend`, sin puertos publicados, así que el navegador no puede llegar a
  ellos.
- **Consultas complejas de consolidación.** `searchPackages` combina vuelo + hotel + auto de un mismo
  destino y fechas y calcula el precio estimado. `searchFlights`, `searchHotels` y `searchCars` aceptan
  filtros: escalas, estrellas, categoría y presupuesto.
- **Mutaciones de reserva.** `bookPackage` (y `register`, `login`, `logout`).
- **Sin over-fetching**, de extremo a extremo:
  1. el frontend pide solo lo que pinta, con fragments y tipos generados (GraphQL Codegen);
  2. el gateway traduce la selección del cliente a una query de Hasura **con solo esas columnas**;
  3. los `DataLoader` evitan el problema N+1.

**Dónde está.**
- [schema.py:606](../services/api-gateway/schema.py#L606): `search_packages`.
- [schema.py:288](../services/api-gateway/schema.py#L288): `_selection_names`, que traduce la selección
  a columnas.
- `FLIGHT_FIELDS` en [schema.py:215](../services/api-gateway/schema.py#L215).
- [frontend/src/graphql/operations.ts](../frontend/src/graphql/operations.ts): fragments `FlightCard`,
  `HotelCard` y `CarCard`.
- [frontend/nginx.conf](../frontend/nginx.conf): proxy de `/graphql`.

**Cómo demostrarlo** (paso 3 del guion).
- En *DevTools → Network*, filtrar `graphql` y abrir la petición `SearchOffers`: el *payload* trae solo
  los campos de los fragments y la respuesta trae exactamente esos campos.
- Comparar con el tipo `FlightOffer` del contrato, que tiene más campos de los que se piden.

### 4.3 Patrón SAGA

**Cómo se cumple.**
- **SAGA orquestada**: `RESERVE_FLIGHT → RESERVE_HOTEL → RESERVE_CAR → PROCESS_PAYMENT` (pivote) →
  confirmaciones → factura.
- Ante un fallo antes del pivote, la compensación es **automática y en orden inverso**. Si el auto
  falla, se cancelan auto, hotel y vuelo, y el inventario vuelve a su valor previo.
- Consistencia:
  - idempotencia por `saga_id` y por `Idempotency-Key`;
  - *tombstones* para cancelaciones que llegan antes que la reserva;
  - `SELECT … FOR UPDATE` contra la sobreventa;
  - recuperación tras un reinicio del orquestador.

**Dónde está.**
- [saga.py:71](../services/orders-service/app/saga.py#L71): `execute_saga`, los pasos.
- [saga.py:177](../services/orders-service/app/saga.py#L177): `_run_step`, reintentos y registro de
  cada intento.
- [saga.py:359](../services/orders-service/app/saga.py#L359): `_compensate`.
- [libs/common/wandersync_common/reservations.py](../libs/common/wandersync_common/reservations.py):
  reserva, cancelación y confirmación idempotentes.
- Diagramas en [saga.md](saga.md).

**Cómo demostrarlo** (pasos 4 y 5 del guion).
- **Happy path**: checkout con *Ninguno*. La línea de tiempo muestra los 8 pasos en verde, la orden
  queda **Confirmada** y aparece la factura `WS-…`.
- **Compensación**: checkout con *Auto*. `RESERVE_CAR` falla en rojo y aparecen
  *Compensación: Reserva del auto*, *…del hotel* y *…del vuelo*. La orden queda **Cancelada (compensada)**.
- **Inventario restaurado**: los asientos, habitaciones y autos disponibles de la oferta vuelven al
  valor anterior. Se ve buscando de nuevo la misma oferta, y lo verifica `tests/e2e/test_saga.py`.
- Prueba automatizada: `tests/e2e/test_saga.py` (happy path + fallos en hotel, auto y pago).

### 4.4 Computación distribuida con Dask

Ver §3.2. Además:
- el escalado horizontal se hace con `--scale dask-worker=N`;
- los workers comparten un límite de ritmo **global** por fuente (Prefect `rate_limit`), así que más
  workers no significa más presión sobre los sitios reales.

### 4.5 Orquestación y observabilidad con Prefect

**Cómo se cumple.**
- **Flow** `ingest-travel-data`, con subflows por catálogo y un `DaskTaskRunner` que envía las tareas
  al clúster Dask.
- **Retries explícitos**:
  - `retries=3`, backoff exponencial y jitter;
  - `retry_condition_fn` que **solo** reintenta fallos transitorios (red, 5xx, timeout);
  - los bloqueos (CAPTCHA, 429) y la cuota agotada no se reintentan, por la política de scraping.
- **Fallos simulados** para la demo: parámetro `simulate_fault_rate`.
- **Schedules**: vuelos y autos cada hora, hoteles a diario. **Artefactos**: tabla resumen e
  incidencias de cada ingesta.

**Dónde está.**
- [ingest.py:65](../data-pipeline/flows/ingest.py#L65): `retry_only_transient`.
- [ingest.py:76](../data-pipeline/flows/ingest.py#L76): `RETRY_POLICY`.
- [ingest.py:279](../data-pipeline/flows/ingest.py#L279): el flow.
- [serve.py](../data-pipeline/flows/serve.py): deployments y schedules.

**Cómo demostrarlo** (paso 2 del guion).
- En la UI de Prefect: *Deployments → vuelos-y-autos → Run → Custom run* con `catalogs=["cars"]` y
  `simulate_fault_rate=0.4`.
- En la corrida se ven tareas en **AwaitingRetry / Retrying** y luego **Completed**, y la pestaña
  *Artifacts* muestra el resumen.
- Prueba: `python scripts/run_service_tests.py ingest`. Por ejemplo, la última ejecución dio
  *23 de 30 búsquedas necesitaron reintentos (máx. 4 intentos)*.

---

## §5. Ciberseguridad por diseño

Documento completo: [seguridad/README.md](seguridad/README.md). Prueba:
`python scripts/run_service_tests.py security` → **15 passed**.

### Session Fixation + hashing robusto

**Cómo se cumple.**
- El ID de sesión **siempre** lo genera el servidor (`secrets.token_urlsafe(32)`) en cada login, y el
  anterior se **destruye** en Redis.
- Cookie `HttpOnly` y `SameSite=Strict`; además, cabecera CSRF obligatoria en las mutaciones.
- Contraseñas con **Argon2id** (`m=64 MiB, t=3, p=4`).

**Dónde está.**
- [auth-service/app/router.py:95](../services/auth-service/app/router.py#L95): `create_session`, que
  destruye `previous_session_id` y crea un ID nuevo.
- [auth-service/app/router.py:31](../services/auth-service/app/router.py#L31): `PasswordHasher` Argon2id.
- [schema.py:891](../services/api-gateway/schema.py#L891): `login` en el gateway.

**Cómo demostrarlo.**
- *DevTools → Application → Cookies*: anotar `ws_session` antes de iniciar sesión, iniciar sesión y
  ver que el valor **cambió**.
- Mostrar el hash en la BD con el compose de depuración:
  `SELECT password_hash FROM auth.users LIMIT 1;` → `$argon2id$v=19$m=65536,t=3,p=4$…`.
- Pruebas `test_session_fixation_planted_id_is_replaced` y `test_password_stored_with_argon2id`.

### Rate limiting en rutas sensibles

**Cómo se cumple.**

| Ruta | Límite | Clave |
|---|---|---|
| Login | 5/min | IP |
| Registro | 3/min | IP |
| Checkout (`bookPackage`) | 3/min | usuario |
| Pago (`orders-service`) | 10/min | usuario |

Los contadores son atómicos en Redis. Nginx reescribe `X-Forwarded-For`, así que el límite no se puede
evadir falsificando la IP.

**Dónde está.**
- [services/api-gateway/limiter.py](../services/api-gateway/limiter.py).
- [services/orders-service/app/limiter.py:37](../services/orders-service/app/limiter.py#L37).

**Cómo demostrarlo.**
- Intentar iniciar sesión con una contraseña incorrecta 6 veces seguidas: la sexta muestra
  *"Demasiados intentos. Espera un momento y vuelve a intentarlo."* (`RATE_LIMITED`). Hacerlo al
  final de la demo, porque bloquea el login desde esa IP durante un minuto.
- Pruebas `test_login_rate_limited_per_ip`, `test_checkout_rate_limited_per_user` y
  `test_payment_rate_limited_in_orders_service`.

### Supply chain security

**Cómo se cumple.**
- Auditoría formal con pip-audit, npm audit y Trivy sobre lo que realmente se despliega, con informe
  **antes y después**:
  - Python: 53 vulnerabilidades → **0**;
  - hallazgos corregibles en las imágenes propias → **0**;
  - frontend → 0.
- *Lockfiles* con hashes SHA-256 instalados con `--require-hashes`, que evitan paquetes alterados.
- CI en GitHub Actions y Dependabot.

**Dónde está.**
- [docs/seguridad/antes/RESUMEN.md](seguridad/antes/RESUMEN.md) y
  [docs/seguridad/despues/RESUMEN.md](seguridad/despues/RESUMEN.md), con su JSON de evidencia.
- [scripts/security_audit.py](../scripts/security_audit.py).
- `services/*/requirements.lock`.
- [.github/workflows/security.yml](../.github/workflows/security.yml).

**Cómo demostrarlo.**
- Abrir los dos `RESUMEN.md` lado a lado.
- Mostrar la pestaña *Actions* de GitHub con el workflow `security` en verde: 17 jobs.
- Explicar los riesgos aceptados (§3.4 del documento de seguridad).

---

## §6. Entregables

| Entregable | Dónde |
|---|---|
| Repositorio limpio con microservicios, frontend, Dockerfile por servicio y `docker-compose.yml` | Rama `prod` de https://github.com/Jorgealis/WanderSync-Travel-Solutions |
| Documento técnico: diagramas de arquitectura, secuencias SAGA (éxito y compensación) y justificación técnica | [documento-tecnico.pdf](documento-tecnico.pdf) (fuentes: [arquitectura.md](arquitectura.md), [saga.md](saga.md), [seguridad/README.md](seguridad/README.md)) |
| Demostración en vivo (a) Prefect, (b) Dask, (c) GraphQL desde el frontend, (d) fallo SAGA con compensación | [demo-guion.md](demo-guion.md), pasos 2, 2, 3 y 5 |

---

## §7. Rúbrica: evidencia por criterio

| Criterio (peso) | Qué pide el nivel *Excelente* | Evidencia en WanderSync |
|---|---|---|
| **Arquitectura y Dockerización (15 %)** | Despliegue automatizado con `docker compose up`; microservicios aislados y bien configurados | 17 contenedores *healthy* sin pasos manuales; un esquema y un usuario de BD por servicio; red interna; migraciones, Hasura, Prefect y primera ingesta automáticos |
| **API Gateway GraphQL y persistencia (15 %)** | Gateway funcional, consultas y mutaciones sin over-fetching, integración fluida con la BD | Selección del cliente → columnas en Hasura; fragments y Codegen; DataLoader; `searchPackages`; Hasura sobre Postgres |
| **SAGA y consistencia (25 %)** | Happy path impecable y compensaciones automáticas ante fallos simulados | 4 puntos de fallo seleccionables desde la UI; línea de tiempo en vivo; idempotencia, tombstones y recuperación; `test_saga.py` en verde |
| **Dask + Prefect (25 %)** | Workers de Dask con scraping/ingesta asíncrona integrados con Prefect, retries y monitoreo | Scraping real en Dask lanzado por flows de Prefect; retries condicionados y fallos simulables; artefactos; dashboard de Dask; escalado; `test_ingest_e2e.py` en verde |
| **Ciberseguridad y resiliencia (20 %)** | Session Fixation, Argon2id/bcrypt, rate limiting y reporte formal de supply chain | 15 pruebas de seguridad; Argon2id; 4 límites; auditoría antes/después; CI + Dependabot; contenedores endurecidos |

## Resumen de pruebas automatizadas

| Suite | Comando | Resultado |
|---|---|---|
| Pipeline (scrapers, normalización, cuota, persistencia) | `python scripts/run_service_tests.py pipeline` | 75 passed |
| Contrato de reservas (vuelos, hoteles, autos) | `python scripts/run_service_tests.py flights hotels cars` | 3 × 14 passed |
| Seguridad | `python scripts/run_service_tests.py security` | 15 passed |
| E2E ingesta (Prefect + Dask) | `python scripts/run_service_tests.py ingest` | 5 passed |
| E2E SAGA (gateway → SAGA → inventario) | `python -m pytest tests/e2e/test_saga.py` | 1 passed (4 escenarios) |
| CI (GitHub Actions) | push a `prod` | 17 jobs en verde |
