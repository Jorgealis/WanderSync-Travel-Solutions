# Fuente 2 — Hotelbeds (hoteles)

| | |
|---|---|
| **Catálogo** | Hoteles (`hotels.room_offers`) |
| **Tipo de fuente** | **API oficial** (no es scraping de HTML): JSON documentado, con claves propias |
| **Entorno** | Evaluación: `https://api.test.hotelbeds.com`. Según Hotelbeds, usa servidores idénticos a producción, sin reservas ni cobros reales |
| **Autenticación** | Cabecera `Api-key` + `X-Signature` = SHA-256(`api_key` + `secret` + timestamp Unix) |
| **Límite** | **50 peticiones por día** (entorno de evaluación) |
| **Credenciales** | `HOTELBEDS_API_KEY` / `HOTELBEDS_API_SECRET` en el `.env` de cada desarrollador (nunca en el repositorio) |
| **Prueba** | [`data-pipeline/tools/probe_hotelbeds.py`](../../data-pipeline/tools/probe_hotelbeds.py) (2 peticiones) |

## Por qué Hotelbeds (evaluación del 2026-10-09, tarea 2.5)

Se evaluaron 15 fuentes de hoteles (registro completo en PROGRESO.md §1.4). Ninguna permitía scraping de resultados con fechas sin incumplir la política del proyecto:

- **Prohibidas por `robots.txt`:** Google Hotels (redirige a `/travel/search`), Despegar, Hoteles.com, Trivago, Hostelworld, Bing, Viajes Falabella y Airbnb.
- **Con CAPTCHA o `403`:** TripAdvisor y Despegar.
- **Sin respuesta:** Expedia, PriceTravel, Almundo y HotelsCombined.
- **Agoda:** permitida, pero solo funciona ejecutando JavaScript (Playwright). El equipo la descartó.
- **Amadeus Self-Service:** cerró su portal el 2026-07-17.

Hotelbeds es un mayorista de hoteles con una API pública documentada y un registro gratuito para desarrolladores. El enunciado admite "plataformas públicas". **El scraping de HTML del proyecto lo cubre Google Flights**; Hotelbeds aporta una segunda clase de fuente detrás de la misma interfaz de ingesta (Dask + Prefect + reintentos).

## Prueba (2026-10-09)

| Petición | Resultado |
|---|---|
| `GET /hotel-content-api/1.0/locations/destinations?countryCodes=CO` | `200`. Los códigos de destino **coinciden con los IATA** del proyecto: `MDE`, `CTG`, `BOG`, `ADZ`, `CLO`, `BAQ`… |
| `POST /hotel-api/1.0/hotels` (MDE, 16→19 oct, 1 habitación, 2 adultos) | `200`, **67 hoteles con disponibilidad** |

Ejemplo real:

```json
{
  "code": 104915, "name": "NH Collection Medellín Royal",
  "categoryCode": "5EST", "categoryName": "5 STARS",
  "destinationCode": "MDE", "zoneName": "Medellin",
  "latitude": "6.19745633400000000000", "longitude": "-75.57255684000000000000",
  "minRate": "312.50", "maxRate": "669.97", "currency": "EUR",
  "room_example": { "code": "DBL.SU", "name": "SUPERIOR ROOM", "net": "312.50",
                    "boardName": "ROOM ONLY", "adults": 2, "allotment": 37 }
}
```

## Qué aporta frente al scraping

| Dato | Google Flights (scraping) | Hotelbeds (API) |
|---|---|---|
| ID estable de la fuente | No (hash propio) | **Sí** (código de hotel + habitación + régimen) |
| Cupos disponibles | No | **Sí** (`allotment`) → inventario inicial real |
| Coordenadas | — | Sí |
| Formato | Texto en español para lectores de pantalla | JSON estructurado |

## Límites conocidos

| Límite | Consecuencia | Cómo se maneja |
|---|---|---|
| **50 peticiones/día** | No se pueden consultar hoteles cada hora | Ingesta de hoteles **diaria** y separada de la de vuelos (ver plan de cuota) |
| **Precios en EUR** | El catálogo está en USD | Conversión EUR → USD en la limpieza (tarea 2.9); el original se guarda en `price_original` |
| **Tarifa neta (mayorista)** | No es el precio al público, sino lo que paga una agencia | Se documenta en la interfaz como precio de referencia |
| **Datos anómalos en evaluación** | Un hotel mostró "desde 497.102 EUR" (probablemente un valor en COP mal etiquetado) | La limpieza (2.9) descarta precios por noche fuera de un rango razonable |
| **La disponibilidad no trae dirección ni puntaje** | `address` y `rating` vacíos | Son opcionales en el contrato. La Content API tiene la dirección (opcional en el futuro) |
| **Categorías que no son de estrellas** | Hostales o apartamentos sin número de estrellas | `stars` NULL y `category_name` con el texto original |
| **Precio por estadía, no por noche** | `net` es el total del rango de fechas | `price_per_night = price_total / nights` |

## Implementación (tarea 2.6)

| Pieza | Archivo | Detalle |
|---|---|---|
| Cliente | [`scrapers/hotelbeds.py`](../../data-pipeline/scrapers/hotelbeds.py) | `POST /hotel-api/1.0/hotels` firmado; una oferta por hotel + habitación + régimen, con la tarifa más barata |
| Cuota | [`scrapers/quota.py`](../../data-pipeline/scrapers/quota.py) | Contador diario (UTC) en el volumen `ingest-state`, compartido por todos los workers y protegido con un bloqueo de archivo. Se reserva **antes** de cada petición; al llegar a `HOTELBEDS_DAILY_BUDGET` (45) lanza `DailyQuotaExceeded` sin llamar a la API |
| Pruebas | [`tests/test_hotelbeds.py`](../../data-pipeline/tests/test_hotelbeds.py), [`tests/test_quota.py`](../../data-pipeline/tests/test_quota.py) | Respuesta real reducida (CTG, 68 hoteles), firma, errores 401, cuota agotada y cambio de día |

Uso manual (consume 1 petición): `docker compose run --rm --no-deps prefect-worker python -m scrapers.hotelbeds CTG 2026-10-16 3`

### Variedad observada en la respuesta real (CTG, 2026-10-09)

- **68 hoteles, 326 ofertas, 0 tarifas descartadas**, todas en EUR y todas con `allotment`.
- **Categorías:** `5EST`, `4EST`, `3EST`, `2EST`, `5LUX`, `H4_5` ("4 STARS AND A HALF" → 4), `H3_5`, `APTH3` ("APARTHOTEL 3*" → 3), `BOU` (boutique → sin estrellas) y `SPC` (sin categoría oficial → sin estrellas).
- **Prefijos de habitación:** `DBL`, `SUI`, `TWN`, `JSU`, `FAM` (tipos conocidos) y `ROO`, `TPL`, `QUA`, `STU`, `APT`, `BUN`, `DBT`, `CTG` (→ `OTHER`, con el nombre original en `room_name`).

## Plan de cuota

Ciudades destino de `INGEST_ROUTES`: **MDE, CTG, SMR, BOG, ADZ** (5).

| Configuración | Peticiones por ejecución | ¿Cabe en 50/día? |
|---|---|---|
| 5 ciudades × 3 fechas × 3 estadías (`3,5,7` noches) | 45 | ❌ Sin margen para reintentos |
| **5 ciudades × 3 fechas × 2 estadías (`3,5` noches)** | **30** | ✅ **Recomendada**: 1 vez al día, con 20 de margen para reintentos y pruebas |
| 5 ciudades × 3 fechas × 1 estadía | 15 | ✅ Holgada |

La ingesta de hoteles llevará su propio contador diario y se detendrá antes de agotar la cuota.
