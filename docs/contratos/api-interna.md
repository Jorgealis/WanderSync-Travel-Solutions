# Contrato — API REST interna entre servicios

Estos endpoints **no se publican fuera de Docker**: solo son accesibles en la red interna `backend`. El frontend nunca los llama; todo pasa por el gateway GraphQL.

```
frontend ──GraphQL──▶ api-gateway ──REST──▶ auth-service
                           │       ──REST──▶ orders-service ──REST──▶ flights | hotels | cars
                           └──GraphQL──▶ hasura (catálogo, solo lectura)
```

## 1. Convenciones comunes

### Cabeceras

| Cabecera | Dirección | Obligatoria | Descripción |
|---|---|---|---|
| `X-Internal-Token` | entrante | Sí (salvo `/health`) | Secreto compartido `INTERNAL_API_TOKEN`. Si falta o no coincide → `401`. Es defensa en profundidad: aunque alguien llegue a la red interna, no puede invocar los servicios |
| `X-Correlation-ID` | ambas | Sí | UUID generado por el gateway por cada petición GraphQL. Se propaga a todas las llamadas y se escribe en todos los logs |
| `X-User-ID` | gateway → orders | En `/orders*` | ID del usuario autenticado. Solo el gateway lo establece, después de validar la sesión |
| `X-Simulate-Failure` | orders → dominio | No | `true` hace fallar la reserva a propósito. Se ignora si `ENABLE_FAULT_INJECTION != true` |

### Formatos

- JSON `snake_case`. Fechas ISO 8601 UTC. **Dinero como string** (`"349.90"`).
- Todos los servicios exponen `GET /health` → `200 {"status": "ok"}`. Es lo que usa el `healthcheck` de Docker; verifica la conexión a la base de datos (y a Redis, si el servicio lo usa).

### Formato de error (todas las respuestas 4xx/5xx)

```json
{
  "error": {
    "code": "INSUFFICIENT_AVAILABILITY",
    "message": "Only 1 seat(s) available, requested 2",
    "details": { "available": 1, "requested": 2 }
  }
}
```

### Clasificación de errores para la SAGA

Esta regla decide si el orquestador **reintenta** o **compensa**:

| Respuesta | Tipo | Qué hace el orquestador |
|---|---|---|
| `2xx` | Éxito | Pasa al siguiente paso |
| `4xx` (404, 409, 422) | **Fallo de negocio**, no recuperable | Compensa de inmediato, sin reintentar |
| `5xx`, timeout, error de conexión | **Fallo transitorio** | Reintenta hasta `SAGA_MAX_RETRIES` con backoff exponencial (`SAGA_RETRY_BACKOFF_SECONDS × 2^n`). Si se agotan los intentos, compensa |

Timeout por llamada: `SAGA_STEP_TIMEOUT_SECONDS`. **Las compensaciones también se reintentan**, pero sin límite práctico (backoff con tope de 30 s), porque deben completarse. Por eso son idempotentes.

---

## 2. Servicios de dominio: flights-service, hotels-service, cars-service

Los tres exponen **exactamente el mismo contrato**. Solo cambia la tabla de ofertas y de inventario.

| Servicio | URL interna | Inventario | `quantity` significa |
|---|---|---|---|
| flights-service | `http://flights-service:8000` | `seats_available` | pasajeros |
| hotels-service | `http://hotels-service:8000` | `rooms_available` | habitaciones |
| cars-service | `http://cars-service:8000` | `units_available` | vehículos (1) |

Las reservas se identifican por **`saga_id`**: una SAGA tiene como máximo una reserva por servicio. Así el orquestador puede compensar aunque nunca haya recibido el ID de la reserva (por ejemplo, tras un timeout).

### `POST /reservations` — reservar (paso de la SAGA)

```json
// Request
{
  "saga_id": "6f1c...",
  "order_id": "a93b...",
  "offer_id": "0d4e...",
  "quantity": 2
}
```

Comportamiento, dentro de una transacción:
1. Si ya existe una reserva con ese `saga_id`:
   - con estado `RESERVED` o `CONFIRMED` → devuelve `200` con la reserva existente (**replay idempotente**, sin descontar inventario otra vez);
   - con estado `CANCELLED` (tombstone o compensada) → `409 RESERVATION_CANCELLED`.
2. `SELECT ... FOR UPDATE` sobre la oferta y verificación de disponibilidad.
3. Descuento del inventario e inserción de la reserva con `unit_price` tomado **de la oferta** (no del cliente).

| Código | `error.code` | Caso |
|---|---|---|
| `201` | — | Reserva creada |
| `200` | — | Ya existía (replay) |
| `404` | `OFFER_NOT_FOUND` | La oferta no existe |
| `409` | `INSUFFICIENT_AVAILABILITY` | No hay cupo |
| `409` | `RESERVATION_CANCELLED` | La SAGA ya compensó este servicio |
| `409` | `SIMULATED_FAILURE` | Se envió `X-Simulate-Failure: true` (no se toca el inventario) |
| `422` | `VALIDATION_ERROR` | Cuerpo inválido |

```json
// Response 201 / 200
{
  "id": "c27a...",
  "saga_id": "6f1c...",
  "order_id": "a93b...",
  "offer_id": "0d4e...",
  "quantity": 2,
  "unit_price": "180.00",
  "total_price": "360.00",
  "currency": "USD",
  "status": "RESERVED",
  "created_at": "2026-10-03T15:00:00Z",
  "updated_at": "2026-10-03T15:00:00Z"
}
```

### `POST /reservations/{saga_id}/cancel` — compensación

Sin cuerpo. Es **idempotente y siempre termina en `200`** salvo error de infraestructura.

| Estado previo | Efecto | Respuesta |
|---|---|---|
| `RESERVED` | Restaura el inventario y pasa a `CANCELLED` | `200` |
| `CANCELLED` | Nada (ya estaba cancelada) | `200` |
| No existe | Inserta un **tombstone** `CANCELLED` (ver [modelo-datos.md](modelo-datos.md)) | `200` |
| `CONFIRMED` | Nada | `409 RESERVATION_ALREADY_CONFIRMED` (no debe ocurrir: las confirmaciones van después del pivote) |

### `POST /reservations/{saga_id}/confirm` — confirmación (después del pago)

Sin cuerpo. Es idempotente: `RESERVED` → `CONFIRMED` (`200`); si ya está `CONFIRMED`, `200`; si está `CANCELLED` o no existe, `409`/`404`.

### `GET /reservations/{saga_id}`

`200` con la reserva o `404 RESERVATION_NOT_FOUND`. Sirve para depuración y pruebas E2E.

---

## 3. orders-service — `http://orders-service:8000`

Contiene las órdenes, la facturación, el pago simulado y el **orquestador SAGA**. Todos los endpoints `/orders*` exigen `X-User-ID`.

### `POST /orders` — iniciar la reserva de un paquete

```json
// Request (X-User-ID: <uuid>)
{
  "flight_offer_id": "0d4e...",
  "hotel_offer_id": "77aa...",
  "car_offer_id": "9be1...",
  "passengers": 2,
  "rooms": 1,
  "idempotency_key": "e0b4...",
  "simulate_failure_at": "CAR"
}
```

1. Si ya existe una orden con `(user_id, idempotency_key)` → `200` con esa orden.
2. Si no, crea la orden (`PENDING`) y la `saga_instance` (`STARTED`) **en la misma transacción**, responde `202` y lanza la SAGA en segundo plano.

| Código | `error.code` | Caso |
|---|---|---|
| `202` | — | Orden creada; la SAGA corre en segundo plano |
| `200` | — | Replay idempotente |
| `422` | `VALIDATION_ERROR` | |
| `429` | `RATE_LIMITED` | `RATE_LIMIT_PAYMENT` por usuario (defensa en profundidad, tarea 5.2) |

Respuesta: el mismo objeto que `GET /orders/{id}`.

### `GET /orders/{id}`

Devuelve la orden con la SAGA, sus pasos, el pago y la factura. Si la orden no existe **o pertenece a otro usuario** → `404 ORDER_NOT_FOUND`. Se usa 404 y no 403 para no revelar que la orden existe.

```json
{
  "id": "a93b...",
  "user_id": "1f00...",
  "status": "CANCELLED",
  "flight_offer_id": "0d4e...",
  "hotel_offer_id": "77aa...",
  "car_offer_id": "9be1...",
  "passengers": 2,
  "rooms": 1,
  "subtotal": null,
  "taxes": null,
  "total_amount": null,
  "currency": "USD",
  "saga": {
    "id": "6f1c...",
    "status": "COMPENSATED",
    "current_step": "RESERVE_CAR",
    "simulate_failure_at": "CAR",
    "failure_reason": "SIMULATED_FAILURE at RESERVE_CAR",
    "steps": [
      {"step": "RESERVE_FLIGHT", "action": "EXECUTE",    "status": "SUCCEEDED", "attempt": 1, "external_ref": "c27a...", "error_code": null, "error_message": null, "started_at": "...", "finished_at": "..."},
      {"step": "RESERVE_HOTEL",  "action": "EXECUTE",    "status": "SUCCEEDED", "attempt": 1, "external_ref": "d11f...", "error_code": null, "error_message": null, "started_at": "...", "finished_at": "..."},
      {"step": "RESERVE_CAR",    "action": "EXECUTE",    "status": "FAILED",    "attempt": 1, "external_ref": null, "error_code": "SIMULATED_FAILURE", "error_message": "...", "started_at": "...", "finished_at": "..."},
      {"step": "RESERVE_CAR",    "action": "COMPENSATE", "status": "SUCCEEDED", "attempt": 1, "external_ref": null, "error_code": null, "error_message": null, "started_at": "...", "finished_at": "..."},
      {"step": "RESERVE_HOTEL",  "action": "COMPENSATE", "status": "SUCCEEDED", "attempt": 1, "external_ref": "d11f...", "error_code": null, "error_message": null, "started_at": "...", "finished_at": "..."},
      {"step": "RESERVE_FLIGHT", "action": "COMPENSATE", "status": "SUCCEEDED", "attempt": 1, "external_ref": "c27a...", "error_code": null, "error_message": null, "started_at": "...", "finished_at": "..."}
    ]
  },
  "payment": null,
  "invoice": null,
  "created_at": "...",
  "updated_at": "..."
}
```

El paso que falló **también se compensa** (`RESERVE_CAR / COMPENSATE`), porque ante un timeout el orquestador no sabe si la reserva llegó a ejecutarse. El tombstone hace que esa compensación sea segura.

### `GET /orders?limit=20&offset=0`

Órdenes del usuario de `X-User-ID`, ordenadas por `created_at DESC`. Respuesta: `{"items": [...], "total": 7}`. Cada elemento lleva la SAGA sin `steps`.

---

## 4. Definición de la SAGA (orquestación)

Se clasifican las transacciones según el modelo de Chris Richardson (*Microservices Patterns*):

| # | Paso | Tipo | Servicio | Compensación |
|---|---|---|---|---|
| 1 | `RESERVE_FLIGHT` | Compensable | flights | `POST /reservations/{saga_id}/cancel` |
| 2 | `RESERVE_HOTEL` | Compensable | hotels | `POST /reservations/{saga_id}/cancel` |
| 3 | `RESERVE_CAR` | Compensable | cars | `POST /reservations/{saga_id}/cancel` |
| 4 | `PROCESS_PAYMENT` | **Pivote** | orders (interno) | Reembolso: `payments.status = REFUNDED` |
| 5 | `CONFIRM_FLIGHT` | Retriable | flights | — (se reintenta hasta que funcione) |
| 6 | `CONFIRM_HOTEL` | Retriable | hotels | — |
| 7 | `CONFIRM_CAR` | Retriable | cars | — |
| 8 | `ISSUE_INVOICE` | Retriable | orders (interno) | — |

- **Antes del pivote:** si un paso falla, se compensan en orden inverso todos los pasos ya ejecutados, **incluido el que falló**.
- **El pivote:** si el pago falla, se compensa el propio pago y luego los pasos 3 → 2 → 1. Compensar el pago significa: si llegó a capturarse (por ejemplo, el fallo fue un timeout después de cobrar), se marca `REFUNDED`; si no se capturó, no hace nada. Es la misma lógica que en las reservas: el paso que falló también se compensa.
- **Después del pivote:** los pasos ya no se compensan; se reintentan hasta completarse. La SAGA termina `COMPLETED` y la orden pasa a `CONFIRMED`.
- El subtotal se fija al terminar el paso 3: suma de `total_price` de las tres reservas. Luego se calculan impuestos y total.

### Correspondencia de estados

| `saga_instances.status` | `orders.status` |
|---|---|
| `STARTED` / `COMPENSATING` | `PENDING` |
| `COMPLETED` | `CONFIRMED` |
| `COMPENSATED` | `CANCELLED` |
| `FAILED` (una compensación agotó sus intentos) | `FAILED` |

### Recuperación

Al arrancar, orders-service busca las SAGAs en `STARTED`/`COMPENSATING` y las retoma desde el último paso registrado. Esto es posible porque todos los pasos son idempotentes por `saga_id`.

---

## 5. auth-service — `http://auth-service:8000`

Es dueño de los usuarios (Postgres) y de las sesiones (Redis). El gateway gestiona la cookie, pero **nunca** crea IDs de sesión por su cuenta.

### `POST /users` — registro

```json
// Request
{ "email": "ana@example.com", "password": "********", "full_name": "Ana Pérez" }
```

- Normaliza el email (minúsculas, sin espacios), valida que la contraseña tenga al menos 10 caracteres y la hashea con **Argon2id**.
- `201` → `{"id", "email", "full_name", "created_at"}` · `409 EMAIL_TAKEN` · `422 VALIDATION_ERROR`.

### `POST /sessions` — login con rotación de sesión

```json
// Request
{
  "email": "ana@example.com",
  "password": "********",
  "previous_session_id": "valor-de-la-cookie-actual-o-null",
  "ip": "172.18.0.1",
  "user_agent": "Mozilla/5.0 ..."
}
```

1. Verifica la contraseña. Si el usuario no existe, **igual ejecuta una verificación Argon2 contra un hash ficticio**, para que el tiempo de respuesta no revele qué emails existen.
2. Si los parámetros de Argon2 cambiaron, vuelve a hashear la contraseña (`check_needs_rehash`).
3. **Destruye `previous_session_id`** si venía, y genera un ID nuevo con `secrets.token_urlsafe(32)`. Esto mitiga Session Fixation.
4. `201` → `{"session_id", "expires_at", "user": {...}}` · `401 INVALID_CREDENTIALS`, con el mismo mensaje tanto si el email no existe como si la contraseña es incorrecta.

`POST /users` + `POST /sessions` es lo que el gateway ejecuta para la mutación `register`.

### `GET /sessions/{session_id}` — validar sesión

`200` → `{"user": {...}, "expires_at"}`; renueva el TTL de inactividad sin superar el tiempo absoluto. `404 SESSION_NOT_FOUND` si expiró o no existe. El gateway lo llama en cada petición que trae cookie.

### `DELETE /sessions/{session_id}` — logout

`204` siempre (idempotente).

### `GET /users/{id}`

`200` con el usuario o `404`.

---

## 6. Cookie de sesión (la gestiona el gateway)

| Atributo | Desarrollo | Producción |
|---|---|---|
| Nombre | `ws_session` | `__Host-ws_session` |
| `HttpOnly` | sí | sí |
| `Secure` | no (`http://localhost`) | sí |
| `SameSite` | `Strict` | `Strict` |
| `Path` | `/` | `/` |
| `Max-Age` | `SESSION_ABSOLUTE_TIMEOUT_SECONDS` | ídem |

El gateway **solo** asigna la cookie con el `session_id` que devuelve auth-service tras un login o registro exitoso. Si una petición trae una cookie que auth-service no reconoce, el gateway la borra.
