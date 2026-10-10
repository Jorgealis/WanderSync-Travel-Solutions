# Guion de la demostración en vivo

Duración objetivo: **15–18 minutos**. Cubre los cuatro puntos obligatorios del enunciado (§6):
(a) Prefect monitoreando flujos · (b) tareas distribuidas en Dask · (c) consumo de la API GraphQL
desde el frontend · (d) fallo transaccional con compensaciones SAGA. Agrega seguridad y supply chain
para la rúbrica.

Cada paso indica **Haz** (acción), **Muestra** (qué debe verse) y **Di** (qué explicar). El detalle
de cada requisito, con archivos y líneas, está en [requerimientos.md](requerimientos.md).

---

## 0. Preparación (antes de grabar o de entrar a la sala)

1. Levantar el stack y esperar a que todo esté *healthy*:
   ```bash
   docker compose up -d --wait
   docker compose ps
   ```
   Si otro proyecto ocupa el 4200, usar `PREFECT_HOST_PORT=4201` y
   `PREFECT_UI_API_URL=http://localhost:4201/api` en `.env` y reemplazar 4200 por 4201 en este guion.
2. Comprobar que hay catálogo: en `http://localhost:3000`, buscar Bogotá → Medellín con la primera
   fecha sugerida y verificar que aparecen vuelos, hoteles y autos.
3. Tener una cuenta creada (pantalla *Crear cuenta*) y **la sesión cerrada** (para mostrar la rotación
   de la cookie en el paso 6).
4. Abrir estas pestañas en el navegador:
   - `http://localhost:3000` (con DevTools abierto en *Network*, filtro `graphql`);
   - `http://localhost:4200` (Prefect → *Runs*);
   - `http://localhost:8787` (Dask → *Status*).
5. Abrir el editor con estos archivos:
   - `services/orders-service/app/saga.py`;
   - `data-pipeline/flows/ingest.py`;
   - `services/auth-service/app/router.py`;
   - `docker-compose.yml`;
   - `docs/saga.md` (en vista previa, para los diagramas).
6. *(Opcional)* Para mostrar Hasura y la BD:
   `docker compose -f docker-compose.yml -f docker-compose.debug.yml up -d` (consola en `:8080`).
7. Verificar que `.env` tiene `ENABLE_FAULT_INJECTION=true` y `SAGA_STEP_DELAY_SECONDS=1`.

> **Plan B**: si Google Flights o Hotelbeds no responden durante la demo (red de la sala o cuota del
> día), mostrar una corrida anterior completada en Prefect. Para los reintentos se usa el catálogo de
> autos, que es la fuente simulada y siempre está disponible.

---

## 1. Introducción y arquitectura (2 min)

**Haz:** mostrar el diagrama de componentes de `docs/arquitectura.md` y luego en la terminal:

```bash
docker compose ps
```

**Muestra:** 17 contenedores *healthy*:
- `frontend`, `api-gateway`, `auth`, `flights`, `hotels`, `cars` y `orders`;
- `postgres`, `redis` y `hasura`;
- `dask-scheduler` y tres `dask-worker`;
- `prefect-server` y `prefect-worker`;
- `mock-car-rental`.

**Di:**
> "WanderSync vende paquetes de vuelo, hotel y auto. Todo el sistema se levanta con un solo
> `docker compose up`: migraciones, metadata de Hasura, deployments de Prefect y hasta la primera
> ingesta se aplican solos. Cada microservicio —vuelos, hoteles, autos, órdenes y el gateway— tiene su
> Dockerfile, su esquema y su usuario de base de datos. Los servicios internos viven en una red sin
> salida a Internet; solo se publican el frontend y los paneles de Prefect y Dask."

---

## 2. Ingesta distribuida: Prefect (a) + Dask (b) (4 min)

> Lanzar esta corrida **primero**: con reintentos tarda unos 4–5 minutos y se puede volver a ella
> mientras se muestra el resto.

**Haz:** en Prefect → *Deployments* → `ingest-travel-data / vuelos-y-autos` → **Run → Custom run** →
parámetros `catalogs = ["cars"]` y `simulate_fault_rate = 0.4` → *Submit*.

**Muestra:**
1. **Dask** (`:8787` → *Status*): las barras de progreso y el *Task Stream* con tareas en paralelo en
   varios workers. En *Workers*, los tres workers con carga.
2. **Prefect** (*Runs* → la corrida → pestaña *Task Runs* / grafo):
   - tareas `autos MDE 2026-…` en **Running**;
   - algunas en **AwaitingRetry → Retrying → Completed**;
   - el subflow `ingest-cars`.
3. Al terminar, la pestaña **Artifacts** de la corrida: tabla *Resumen de la ingesta de cars*
   (búsquedas OK y fallidas, insertados, actualizados, tasas de cambio) e *Incidencias*.
4. *(Opcional)* La corrida programada de la última hora de `vuelos-y-autos`, con tareas
   `vuelos BOG-MDE …` (Google Flights real).

**Muestra en el código** (`data-pipeline/flows/ingest.py`):
- `RETRY_POLICY` (≈ línea 76): `retries=3`, backoff exponencial y jitter;
- `retry_only_transient` (≈ línea 65): solo se reintentan los fallos transitorios;
- `dask_runner()` (≈ línea 61): `DaskTaskRunner` contra el scheduler;
- `normalize` (≈ línea 175): `dask.bag` reparte la limpieza en el clúster.

**Di:**
> "La recolección nunca corre en los microservicios: un flow de Prefect la orquesta y Dask la ejecuta
> en paralelo, una tarea por búsqueda. Hay tres fuentes: Google Flights con scraping real de HTML,
> la API oficial de Hotelbeds para hoteles y un servicio simulado de autos, que el enunciado permite.
> Prefect reintenta solo los fallos transitorios —red, 5xx, timeouts— con backoff exponencial; un
> bloqueo o un CAPTCHA no se reintenta, por nuestra política de scraping responsable. Aquí forcé un
> 40 % de fallos de red y se ve cómo Prefect los recupera. Además, los precios en COP y EUR se
> normalizan a USD con la TRM y el BCE del día, repartidos con `dask.bag`."

*(Opcional, escalado)* `docker compose up -d --scale dask-worker=4` y en *Workers* aparece el cuarto.

---

## 3. Frontend consumiendo GraphQL (c) (3 min)

**Haz:** en `http://localhost:3000`, Origen **Bogotá**, Destino **Medellín**, primera fecha sugerida,
3 noches, 2 pasajeros → **Buscar**.

**Muestra:**
1. *Paquetes sugeridos* (Opción 1/2/3, con impuestos estimados) y las listas de vuelos (JetSMART,
   LATAM, Wingo con precio en USD y COP), hoteles (estrellas, régimen, disponibilidad) y autos.
2. **DevTools → Network → `graphql`**:
   - todas las peticiones van a `/graphql` (un solo endpoint);
   - abrir `SearchOffers` → *Payload*: la query con los fragments `FlightCard`, `HotelCard`,
     `CarCard` y `searchPackages`;
   - *Response*: llegan **solo** esos campos.
3. **Código**:
   - `frontend/src/graphql/operations.ts`: los fragments;
   - `services/api-gateway/schema.py`: `_selection_names` (≈ línea 288), que convierte lo que pidió el
     cliente en las columnas que se le piden a Hasura.

**Di:**
> "El frontend solo habla con el gateway GraphQL: Nginx reenvía `/graphql` y ningún microservicio es
> accesible desde el navegador. `searchPackages` consolida vuelo, hotel y auto en una sola consulta.
> No hay over-fetching en ningún tramo: el frontend pide con fragments solo lo que pinta, y el gateway
> traduce esa selección a una consulta de Hasura con exactamente esas columnas. Los DataLoader evitan
> el N+1. Hasura es la capa GraphQL nativa sobre Postgres que pide el enunciado."

*(Opcional)* Consola de Hasura (`:8080`, compose de depuración) → query sobre `flight_offers`.

---

## 4. SAGA — camino exitoso (2 min)

**Haz:**
1. **Iniciar sesión** (anotar antes el valor de la cookie para el paso 6, si se hace aquí).
2. En la búsqueda, elegir **Opción 1** → *Continuar al checkout*.
3. En *Panel de demo · Simular fallo en*, dejar **Ninguno** → **Confirmar y pagar**.

**Muestra:** la página de la orden con la **línea de tiempo en vivo**:
- Reserva del vuelo ✓ → del hotel ✓ → del auto ✓;
- Pago ✓;
- Confirmación del vuelo, del hotel y del auto ✓;
- Emisión de la factura ✓.

La orden queda **Confirmada**, con subtotal, impuestos, total, pago `CAPTURED · PAY-…` y factura
`WS-…`.

**Di:**
> "`bookPackage` crea la orden y responde de inmediato; la SAGA corre en segundo plano en
> orders-service, que es el orquestador. Reserva vuelo, hotel y auto, cobra —el pago es el pivote,
> el punto de no retorno— y luego confirma y factura. Cada paso queda persistido, por eso lo vemos en
> vivo."

---

## 5. SAGA — fallo y compensación automática (d) (3 min) ⭐

**Haz:**
1. Volver a la búsqueda, misma Opción 1. **Anotar la disponibilidad** del hotel (p. ej. "15 disp.").
2. Checkout → *Simular fallo en* **Auto** → **Confirmar y pagar**.

**Muestra:**
- La línea de tiempo:
  - ✓ Reserva del vuelo;
  - ✓ Reserva del hotel;
  - ✗ **Reserva del auto — falló: SIMULATED_FAILURE**;
  - ↩ **Compensación: Reserva del auto**;
  - ↩ **Compensación: Reserva del hotel**;
  - ↩ **Compensación: Reserva del vuelo**.
- Estado **Cancelada (compensada)**, sin pago ni factura.
- La disponibilidad del hotel vuelve a ser **la misma de antes** (p. ej. 15 disp.): las habitaciones
  reservadas se devolvieron.
- **Código** `services/orders-service/app/saga.py`:
  - `execute_saga` (≈ línea 71): el `except` que pasa a `COMPENSATING`;
  - `_compensate` (≈ línea 359): reembolso si hubo cobro y cancelación en orden **inverso** con
    `reversed(RESERVATION_SERVICES)`.
- **Diagrama**: `docs/saga.md` §3 (fallo en autos).

**Di:**
> "Este es el caso del enunciado: el auto falla después de haber reservado vuelo y hotel. Sin SAGA
> serían reservas huérfanas. El orquestador detecta el fallo y ejecuta las compensaciones
> automáticamente, en orden inverso. También compensa el paso que falló, porque ante un timeout no
> sabe si la reserva llegó a hacerse; un tombstone hace que eso sea seguro. Las cancelaciones son
> idempotentes y se reintentan hasta completarse, y el inventario vuelve exactamente al valor
> anterior."

*(Opcional)* Repetir con **Pago**: las tres reservas ✓, el pago ✗ y las tres compensaciones. Explicar
el pivote.

*(Opcional, consistencia)* Mencionar que si el orquestador se reinicia a mitad de la SAGA, al arrancar
la retoma (`recover_pending_sagas`), y que la prueba `tests/e2e/test_saga.py` automatiza el happy
path y los fallos en hotel, auto y pago.

---

## 6. Seguridad por diseño (2 min)

**Haz y muestra:**
1. **Session Fixation**:
   - con la sesión cerrada, *DevTools → Application → Cookies → localhost* y anotar `ws_session` (o
     comprobar que no existe);
   - iniciar sesión: `ws_session` tiene **otro valor**;
   - la cookie está marcada `HttpOnly` y `SameSite=Strict`.
2. **Código** `services/auth-service/app/router.py`, `create_session` (≈ línea 95):
   - `_destroy_session(previous_session_id)`;
   - `secrets.token_urlsafe(32)`;
   - `PasswordHasher` (≈ línea 31): Argon2id con 64 MiB, `t=3`, `p=4`.
3. *(Opcional, con el compose de depuración)* `SELECT password_hash FROM auth.users LIMIT 1;` →
   `$argon2id$v=19$m=65536,t=3,p=4$…`.
4. **Pruebas**:
   ```bash
   python scripts/run_service_tests.py security
   ```
   → **15 passed** (Session Fixation, Argon2id, rate limits, CSRF…).
5. **Rate limiting** (al final, porque bloquea el login un minuto): cerrar sesión e intentar entrar 6
   veces con una contraseña errónea. El sexto intento muestra *"Demasiados intentos. Espera un momento
   y vuelve a intentarlo."*

**Di:**
> "Tras cada login el servidor genera un ID de sesión nuevo y destruye el anterior en Redis, así que
> un ID plantado por un atacante no sirve. Las contraseñas usan Argon2id con 64 MiB de memoria. Hay
> rate limiting con contadores en Redis en login (5 por minuto por IP), registro, checkout (3 por
> minuto por usuario) y pago (10 por minuto, en orders-service como defensa en profundidad). Nginx
> reescribe la IP del cliente, así que no se puede evadir falsificando cabeceras."

---

## 7. Supply chain y endurecimiento (1–2 min)

**Haz y muestra:**
1. `docs/seguridad/antes/RESUMEN.md` y `docs/seguridad/despues/RESUMEN.md` lado a lado:
   - pip-audit: 53 → **0**;
   - Trivy en imágenes propias, hallazgos corregibles → **0**;
   - frontend → 0.
2. `docs/seguridad/README.md` §3.4: riesgos aceptados y su mitigación.
3. GitHub → *Actions* → workflow **security** en verde: pip-audit ×8, npm audit, Trivy ×6, *locks*
   y pruebas.
4. `docker-compose.yml`: anclas `x-hardened` (`cap_drop: ALL`, `no-new-privileges`) y `x-readonly`,
   y la red `backend` con `internal: true`.

**Di:**
> "Auditamos lo que realmente se despliega: el inventario instalado en cada imagen con pip-audit, el
> frontend con npm audit y cada imagen con Trivy, incluidas las de terceros y la búsqueda de secretos.
> Corregimos todo lo que tenía parche, fijamos las dependencias con hashes SHA-256 —un paquete
> alterado rompe el build— y lo automatizamos en CI con Dependabot. Lo que queda sin parche está
> documentado como riesgo aceptado, con su mitigación. Además, los contenedores corren sin root, sin
> capacidades del kernel y con disco de solo lectura."

---

## 8. Cierre (30 s)

**Di:**
> "En resumen: microservicios desplegados con un solo comando, un gateway GraphQL sin over-fetching
> sobre Hasura, una SAGA orquestada con compensaciones automáticas, ingesta real distribuida en Dask
> y orquestada por Prefect con reintentos y observabilidad, y seguridad por diseño con evidencia
> automatizada. Todo está documentado en `docs/`, con el documento técnico en PDF."

---

## Preguntas probables y respuestas cortas

| Pregunta | Respuesta |
|---|---|
| ¿Por qué orquestación y no coreografía? | Orden estricto (no se cobra sin las tres reservas), estado visible y persistido, recuperación tras caídas y sin broker. Tabla en `docs/saga.md` §6 |
| ¿Qué pasa si se cae orders-service a mitad de la SAGA? | El estado está en `saga_steps`; al arrancar, `recover_pending_sagas` retoma o compensa. Los pasos interrumpidos quedan como `ORCHESTRATOR_RESTARTED` |
| ¿Y si dos clientes compran el último asiento? | `SELECT … FOR UPDATE` en la oferta: uno reserva y el otro recibe `409 INSUFFICIENT_AVAILABILITY` y su SAGA compensa |
| ¿La ingesta puede pisar el inventario reservado? | No: el upsert solo actualiza precio y metadata, y el usuario `ingest` no tiene permiso de UPDATE sobre las columnas de inventario (lo verifica `test_ingest_e2e.py`) |
| ¿Por qué Hasura y no Supabase? | Mismo resultado (GraphQL nativo sobre Postgres) con un solo contenedor y metadata versionada; Supabase autoalojado trae ~10 servicios que no se usan |
| ¿Es scraping legal? | Solo rutas permitidas por `robots.txt`, ritmo limitado, sin saltar CAPTCHAs; las fuentes que lo prohíben se descartaron (registro en `PROGRESO.md` §1.4). Hoteles usan la API oficial |
| ¿Por qué los autos son simulados? | Las 10 fuentes de autos evaluadas prohíben el scraping o usan anti-bot; el enunciado (§3.1) permite servicios simulados. Aun así pasa por el mismo pipeline, con fallos y paginación reales |
| ¿Cómo evitan el over-fetching? | Fragments en el cliente + traducción de la selección a columnas de Hasura + DataLoader |
| ¿Qué falta para producción? | HTTPS (`SESSION_COOKIE_SECURE=true`), `ENABLE_FAULT_INJECTION=false`, plan de pago de Hotelbeds y una pasarela de pago real |
