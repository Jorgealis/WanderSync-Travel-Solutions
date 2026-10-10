# Seguridad por diseño — WanderSync

Este documento cubre los requisitos de ciberseguridad del enunciado (§5) y es la evidencia formal
de las tareas 5.1–5.8 y 7.2. Todo lo que se afirma aquí se comprueba con una prueba automatizada
o con un informe reproducible.

| Requisito del enunciado | Control implementado | Evidencia |
|---|---|---|
| Session Fixation | El ID de sesión se genera **en el servidor** en cada login; el anterior se destruye | `tests/security/test_security.py::test_session_fixation_planted_id_is_replaced`, `test_each_login_rotates_and_revokes_previous_session` |
| Hashing robusto | **Argon2id** (`m=64 MiB, t=3, p=4`) con rehash automático si cambian los parámetros | `test_password_stored_with_argon2id` (lee el hash real de Postgres) |
| Rate limiting en autenticación | Login 5/min por IP, registro 3/min por IP | `test_login_rate_limited_per_ip`, `test_spoofed_forwarded_for_through_nginx_does_not_bypass_limit` |
| Rate limiting en checkout | `bookPackage` 3/min por usuario (gateway) | `test_checkout_rate_limited_per_user` |
| Rate limiting en pago | 10/min por usuario en `orders-service` (defensa en profundidad) | `test_payment_rate_limited_in_orders_service` |
| Supply chain audit | pip-audit + npm audit + Trivy, informe antes/después, locks con hashes, CI y Dependabot | `docs/seguridad/antes/`, `docs/seguridad/despues/`, `.github/workflows/security.yml` |

Ejecutar toda la suite contra el stack levantado (`docker compose up -d`):

```bash
python scripts/run_service_tests.py security
```

Resultado actual: **15 passed**.

---

## 1. Identidad y sesiones

### 1.1 Diseño

```mermaid
sequenceDiagram
    autonumber
    participant B as Navegador
    participant N as Nginx (frontend)
    participant G as API Gateway (GraphQL)
    participant A as auth-service
    participant R as Redis
    participant P as Postgres (auth)

    B->>N: POST /graphql mutation login (cookie ws_session=X, quizá plantada)
    N->>G: proxy (X-Forwarded-For reescrito por Nginx)
    G->>R: rate limit login:IP (5/min)
    G->>A: POST /login {email, password, previous_session_id: X}
    A->>P: SELECT usuario
    A->>A: Argon2id verify (y rehash si cambian parámetros)
    A->>R: DEL session:X (la sesión anterior deja de existir)
    A->>R: SET session:Y (Y = secrets.token_urlsafe(32), TTL inactividad 30 min)
    A-->>G: {session_id: Y}
    G-->>B: Set-Cookie ws_session=Y; HttpOnly; SameSite=Strict; Max-Age=8h
```

- **Session Fixation**: el ID nunca lo elige el cliente. En cada login se crea uno nuevo con
  `secrets.token_urlsafe(32)` (256 bits) y el que traía el navegador se destruye en Redis
  (`services/auth-service/app/router.py`, función `login`; el gateway envía `previous_session_id`
  en `services/api-gateway/schema.py`). Un ID plantado por un atacante queda inválido.
- **Revocación en el servidor**: `logout` borra la sesión en Redis (no basta con borrar la cookie).
- **Expiración**: 30 min de inactividad (TTL deslizante) y 8 h absolutas.
- **Cookie**: `HttpOnly` (no la lee JavaScript), `SameSite=Strict` y `Secure` configurable para HTTPS
  (`SESSION_COOKIE_SECURE=true` y nombre `__Host-ws_session` en producción).
- **CSRF**: además de `SameSite=Strict`, toda mutación exige la cabecera `X-WanderSync-CSRF: 1`, que
  un formulario de otro sitio no puede enviar.
- **Sin enumeración de usuarios**: mismo error (`INVALID_CREDENTIALS`) para correo inexistente y
  contraseña incorrecta; si el usuario no existe se verifica contra un hash señuelo para que el
  tiempo de respuesta sea el mismo.

### 1.2 Contraseñas: Argon2id

| Parámetro | Valor | Variable |
|---|---|---|
| Algoritmo | Argon2id (ganador de la Password Hashing Competition, recomendado por OWASP) | — |
| Memoria | 65 536 KiB (64 MiB) | `ARGON2_MEMORY_COST_KIB` |
| Iteraciones | 3 | `ARGON2_TIME_COST` |
| Paralelismo | 4 | `ARGON2_PARALLELISM` |
| Longitud de contraseña | 10 a 128 caracteres | `PASSWORD_MIN_LENGTH` (`auth-service`) |

El hash guardado tiene la forma `$argon2id$v=19$m=65536,t=3,p=4$<sal>$<hash>`: la prueba lo lee
directamente de la tabla `auth.users`.

## 2. Protección de la superficie

### 2.1 Rate limiting

Contador atómico en Redis (script Lua `INCR` + `EXPIRE`), compartido por todas las réplicas del
gateway. Al superar el límite el gateway responde el error GraphQL `RATE_LIMITED` con `retryAfter`
y `orders-service` responde HTTP 429 con `Retry-After`.

| Ruta | Límite | Clave | Dónde |
|---|---|---|---|
| `mutation login` | 5 / minuto | IP | `services/api-gateway/schema.py` (`login`) |
| `mutation register` | 3 / minuto | IP | `services/api-gateway/schema.py` (`register`) |
| `mutation bookPackage` (checkout) | 3 / minuto | usuario | `services/api-gateway/schema.py` (`book_package`) |
| `POST /orders/{id}/payment` | 10 / minuto | usuario | `services/orders-service/app/limiter.py` |
| Resto de operaciones | 120 / minuto | IP | `get_context` del gateway |

La IP sale de `X-Forwarded-For`, pero **Nginx la sobrescribe** con la IP real del cliente
(`proxy_set_header X-Forwarded-For $remote_addr`), así que un atacante no puede rotar IPs falsas
para saltarse el límite (prueba `test_spoofed_forwarded_for_through_nginx_does_not_bypass_limit`).

### 2.2 Otras defensas del gateway

- **Límite de profundidad** de consultas GraphQL (8 niveles) contra consultas abusivas.
- **Cabeceras** en Nginx: `Content-Security-Policy` estricta, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`.
- **Privacidad de órdenes**: un usuario no puede leer órdenes de otro (`test_orders_are_private_between_users`).
- **Hasura sin exposición**: sin puertos publicados, consola desactivada y rol `gateway` con
  permisos de solo lectura por columna.

## 3. Cadena de suministro

### 3.1 Herramientas y alcance

| Herramienta | Versión | Qué audita |
|---|---|---|
| `pip-audit` | 2.10.1 | Inventario **real** de cada imagen Python (dependencias directas y transitivas instaladas) |
| `npm audit` | npm 10.9 | Frontend: todas las dependencias y solo las de ejecución (`--omit=dev`) |
| Trivy | 0.75.0 | Cada imagen (propias y de terceros): paquetes del SO, paquetes de lenguaje y **secretos** incrustados |

Reproducir (requiere las imágenes construidas):

```bash
docker compose build
python scripts/security_audit.py despues
```

Genera `docs/seguridad/<etiqueta>/auditoria.json` (evidencia completa) y `RESUMEN.md`.

### 3.2 Antes y después

Línea base (`docs/seguridad/antes/`, 2026-10-10 04:33 UTC) contra estado final
(`docs/seguridad/despues/`):

| Hallazgo | Antes | Después |
|---|---|---|
| pip-audit: vulnerabilidades Python (8 imágenes) | 53 (pip 25.0.1 en todas; Strawberry 0.287.3 en el gateway) | **0** |
| npm audit: dependencias de ejecución (lo que llega al navegador) | 0 | **0** |
| npm audit: dependencias de desarrollo | 10 HIGH (una cadena: `braces`) | 10 HIGH — riesgo aceptado (§3.4) |
| Trivy imágenes propias: hallazgos con corrección disponible | 14 por imagen (19 en el gateway) | **0** |
| Trivy frontend (Nginx) | 1 HIGH (`tiff`) | **0 en todas las severidades** |
| Trivy: secretos en imágenes | 0 | **0** |
| Trivy Hasura | no se pudo analizar | analizado (ver §3.4) |

### 3.3 Correcciones aplicadas (tarea 5.6)

1. **pip 25.0.1 → fuera de las imágenes.** En el build se usa pip 26.2.1. En la imagen final pip se
   desinstala: no se necesita en ejecución y arrastraba sus propias dependencias embebidas
   (`urllib3`, `msgpack`) con vulnerabilidades. La etapa `test` lo reinstala con `ensurepip`.
2. **Strawberry GraphQL 0.287.3 → 0.332.1** (5 advisories), con `graphql-core` 3.3.0.
3. **Locks con hashes SHA-256**: cada servicio tiene `requirements.lock` generado con
   `pip-compile --generate-hashes` (`python scripts/lock_requirements.py`) y las imágenes instalan con
   `pip install --require-hashes`. Si un paquete publicado cambia (paquete comprometido), el build falla.
   El frontend usa `package-lock.json` con `npm ci`.
4. **Parches del sistema operativo**: `apt-get upgrade` (Debian) en las imágenes Python y
   `apk upgrade` (Alpine) en la de Nginx.
5. **Imágenes base fijadas** a versiones concretas (`python:3.12-slim`, `node:22.23.3-alpine`,
   `nginx-unprivileged:1.31.6-alpine`, `postgres:16.15-alpine`, `hasura v2.51.0`).

### 3.4 Riesgos aceptados

| Hallazgo | Por qué se acepta | Mitigación |
|---|---|---|
| 44 HIGH de Debian 13 en las imágenes Python (17 paquetes del SO, p. ej. `libsystemd0`, `login`) | Debian **no ha publicado corrección**; `apt-get upgrade` ya instala todo lo disponible | Ninguno de esos binarios se ejecuta (solo corre `python`/`uvicorn`); contenedores sin capacidades, solo lectura y no-root. El CI vuelve a bloquear en cuanto exista la corrección (`ignore-unfixed`) |
| `braces` ≤ 3.0.3 (npm, 10 HIGH) | Solo en **herramientas de desarrollo** (GraphQL Codegen); no existe versión corregida y `npm audit fix` propone degradar Codegen | No llega al navegador (`npm audit --omit=dev` = 0). El CI bloquea vulnerabilidades moderadas en ejecución y críticas en desarrollo |
| Postgres: Go `stdlib` dentro de `gosu` (1 CRITICAL, 24 HIGH) | Binario de la imagen oficial; solo se usa al arrancar para cambiar de usuario | Red interna sin puertos publicados; proceso como uid 70 sin capacidades extra |
| Redis: `libssl3`/`libcrypto3` | Corregido en Alpine, pendiente de nueva imagen oficial | Red interna; Redis no usa TLS en este despliegue; corre como uid 999 sin capacidades efectivas |
| Hasura: `openssl`, `curl`, `libxml2` (Ubuntu) | Imagen oficial pendiente de reconstrucción | Red interna, sin puertos ni consola; rol `gateway` de solo lectura |

### 3.5 Automatización (tarea 5.8)

`.github/workflows/security.yml` se ejecuta en cada PR, en cada push a `prod`/`main` y cada lunes:

| Job | Qué hace | Falla si… |
|---|---|---|
| `locks` | `scripts/check_locks.py` | `requirements.txt` cambió sin regenerar el lock (p. ej. un PR de Dependabot) |
| `pip-audit` (×8) | Audita cada `requirements.lock` con `--require-hashes` | Hay cualquier vulnerabilidad conocida |
| `npm-audit` | `npm ci`, audit y build (codegen + TypeScript estricto) | Vulnerabilidad ≥ moderada en ejecución o crítica en desarrollo |
| `pipeline-tests` | 75 pruebas del pipeline (scrapers, normalización, cuota) | Alguna prueba falla |
| `trivy` (×6) | Construye la imagen y la escanea | CRITICAL/HIGH **con corrección disponible** o un secreto |

`.github/dependabot.yml` abre PRs semanales agrupados para pip, npm, imágenes Docker y GitHub Actions.

## 4. Endurecimiento de contenedores (tarea 5.7)

| Medida | Dónde | Cómo comprobarlo |
|---|---|---|
| Usuario no-root en todas las imágenes propias (`app`, Nginx uid 101) | Dockerfiles | `docker inspect -f '{{.Config.User}}' <contenedor>` |
| `cap_drop: [ALL]` + `no-new-privileges` en **los 17 contenedores** (Postgres y Redis solo recuperan las capacidades que su entrypoint necesita para bajar de root) | `docker-compose.yml` (`x-hardened`) | `docker inspect -f '{{.HostConfig.CapDrop}}'` |
| Sistema de archivos de **solo lectura** (con `/tmp` en memoria) en los 8 servicios sin estado | `x-readonly` | `docker compose exec flights-service touch /app/x` → `Read-only file system` |
| Red `backend` **interna** (sin salida a Internet) | `networks.backend.internal: true` | desde `flights-service` no se resuelve ningún dominio externo |
| Red `edge` solo para lo que necesita Internet (workers de Dask: scraping) y los paneles | `docker-compose.yml` | desde `dask-worker` sí se conecta a Google Flights y Hotelbeds |
| Solo 3 puertos publicados y en `127.0.0.1`: frontend, Prefect UI, dashboard de Dask | `docker-compose.yml` | `docker compose ps` |
| Postgres, Hasura y el gateway directo solo con `docker-compose.debug.yml` | `docker-compose.debug.yml` | — |
| Sin pip ni herramientas de build en las imágenes finales (multi-stage) | Dockerfiles | `docker compose exec flights-service python -m pip` → `No module named pip` |
| Sin secretos en imágenes ni en Git (`.env` ignorado; Trivy secret scan = 0) | `.gitignore`, Trivy | `docs/seguridad/despues/RESUMEN.md` |

Hallazgo corregido durante el endurecimiento: Redis se arrancaba con `sh -c 'exec redis-server …'`,
lo que se saltaba el paso del entrypoint oficial que cambia al usuario `redis`, así que **corría como
root**. Ahora pasa por `docker-entrypoint.sh` y corre como uid 999 sin capacidades efectivas.
