# Fuente 1 — Google Flights (vuelos)

| | |
|---|---|
| **Catálogo** | Vuelos (`flights.flight_offers`) |
| **URL** | `https://www.google.com/travel/flights?q=Flights from {ORIGEN} to {DESTINO} on {AAAA-MM-DD} one way&hl=es&curr=COP&gl=CO` |
| **Código** | [`data-pipeline/scrapers/google_flights.py`](../../data-pipeline/scrapers/google_flights.py) |
| **Pruebas** | [`data-pipeline/tests/test_google_flights.py`](../../data-pipeline/tests/test_google_flights.py) (sin red, con fixtures de páginas reales) |
| **Validación en vivo** | [`data-pipeline/tools/validate_google_flights.py`](../../data-pipeline/tools/validate_google_flights.py) |

## Por qué es viable (evaluación del 2026-10-03, tarea 2.1)

- `robots.txt` prohíbe `/travel/flights/search` y `/travel/flights/s/`, pero **no** `/travel/flights?q=...`, que es la ruta usada.
- Los resultados vienen **renderizados en el HTML**, sin necesidad de ejecutar JavaScript ni de un navegador automatizado.
- Una petición normal responde `200`, sin CAPTCHA ni desafío anti-bot.

## Cómo se extraen los datos

Cada vuelo trae una etiqueta de accesibilidad (`aria-label`) pensada para lectores de pantalla, por ejemplo:

> A partir de 515270 pesos colombianos. Vuelo con 1 escala de Avianca. Sale de Aeropuerto Internacional Alfonso Bonilla Aragón el viernes, octubre 16 a las 5:55. Llega a … el viernes, octubre 16 a las 9:50. Duración total: 3 h 55 min. Esta escala (1 de 1) es una escala de 1 h 15 min en … El Dorado …

El parser lee esas etiquetas en lugar de las clases CSS, que están ofuscadas y cambian con frecuencia. El texto de accesibilidad es mucho más estable.

## Validación en vivo (2026-10-09, tarea 2.4)

Configuración por defecto: 7 rutas (`INGEST_ROUTES`) × 3 fechas (hoy + 7, 14 y 30 días) = 21 peticiones, con 5 s de pausa entre ellas.

| Resultado | Valor |
|---|---|
| Búsquedas correctas | **21 / 21** |
| Vuelos extraídos | **569** |
| Etiquetas descartadas por el parser | **0** |
| Anomalías (duración publicada ≠ calculada) | **0** |
| Vuelos por búsqueda | entre 5 (CLO→CTG) y 54 (MDE→BOG) |
| Vuelos con escala | 25 |
| Llegadas al día siguiente | 5 (se resuelven bien) |
| Con operador declarado | 258 de 569 |
| Aerolíneas | Avianca 253 · LATAM 168 · JetSMART 81 · Wingo 67 |
| Tiempo por búsqueda | ~6 s (incluida la pausa de 5 s) |
| Bloqueos | ninguno |

Para repetir la validación (por ejemplo, antes de la demo):

```bash
docker compose run --rm --no-deps prefect-worker python -m tools.validate_google_flights
```

## Límites conocidos

| Límite | Consecuencia | Cómo se maneja |
|---|---|---|
| **El parser solo entiende las etiquetas en español** | Si Google cambia la redacción, las etiquetas dejan de interpretarse | Se fuerza `hl=es`. Si ninguna etiqueta se entiende, se lanza `ParseError` (sin reintentos) y las pruebas con fixtures lo detectan |
| **Requiere un User-Agent de navegador** | Con el de `httpx` por defecto, Google redirige a `/travel/flights/unsupported` sin vuelos | `SCRAPER_USER_AGENT`. Si ocurre, `SourceBlockedError` con un mensaje claro |
| **Sin número de vuelo** | `flight_number` queda vacío | El contrato lo permite (tarea 2.2) |
| **Sin cupos disponibles** | No se sabe cuántos asientos quedan | WanderSync asigna `INGEST_DEFAULT_SEATS` al insertar |
| **"A partir de" = tarifa más barata** | Es la tarifa básica: la propia etiqueta aclara que no incluye equipaje de mano en el compartimento superior | Se documenta en la interfaz como "precio desde" |
| **Solo clase económica** | La búsqueda por defecto no incluye otras cabinas | `cabin_class = ECONOMY` |
| **Vuelos con escalas: una sola aerolínea en el texto** | Solo se nombra la aerolínea que vende; los operadores aparecen por tramo | `operated_by` agrupa los operadores sin repetir |
| **Solo aeropuertos de Colombia** | Google muestra horas locales; el parser conoce la zona horaria (UTC−5) solo de aeropuertos colombianos | Suficiente para las rutas del proyecto. Para rutas internacionales habría que agregar zonas horarias por aeropuerto |
| **Sin paginación** | Google muestra hasta ~54 resultados por búsqueda | En las rutas probadas cubre todos los vuelos del día |
| **El ID se deriva de los datos** | Google no publica un ID; si cambia el nombre visible de la aerolínea o el horario, se crea otra oferta | Hash SHA-1 de aerolínea + ruta + horarios + cabina. Los cambios de precio **no** cambian el ID |
| **Precios volátiles** | El mismo vuelo cambió de precio entre dos consultas del mismo día | Es el comportamiento esperado: cada ingesta actualiza `price` y `scraped_at` |
| **Términos de uso de Google** | Desaconsejan el acceso automatizado aunque `robots.txt` permita la ruta | Uso académico, 21 peticiones por hora, pausa de 5 s, sin saltarse protecciones. Se declara como limitación en el documento técnico |
