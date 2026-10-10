# Fuente 3 — RutaFácil (autos, SIMULADA)

| | |
|---|---|
| **Catálogo** | Autos (`cars.car_offers`) |
| **Tipo de fuente** | **Servicio simulado** dentro de Docker Compose (`mock-car-rental`), permitido por la sección 3.1 del enunciado: *"servicios mockeados que simulen la complejidad de dichas fuentes"* |
| **Servicio** | [`services/mock-car-rental`](../../services/mock-car-rental) — `GET /alquiler/{CIUDAD}?recogida=…&devolucion=…&pagina=N` |
| **Scraper** | [`data-pipeline/scrapers/mock_car_rental.py`](../../data-pipeline/scrapers/mock_car_rental.py) |
| **Pruebas** | [`data-pipeline/tests/test_mock_car_rental.py`](../../data-pipeline/tests/test_mock_car_rental.py) |
| **`source`** | `wandersync-mock-cars` |

## Por qué es simulada (tarea 2.7)

Se evaluaron 10 fuentes reales de alquiler de autos y ninguna se puede usar sin incumplir la política de scraping del proyecto (registro completo en PROGRESO.md §1.4):

- **Prohíben la búsqueda en `robots.txt`:** Rentalcars, Discover Cars y Despegar.
- **Bloqueo anti-bot:** Rentcars (Cloudflare) y Localiza (Akamai Bot Manager; la búsqueda real falló y no se reintentó).
- **Sin respuesta o `403`:** Economy Bookings, Hertz, Avis y Europcar.
- **APIs:** Amadeus cerró y Hotelbeds no ofrece autos.

## Qué complejidad simula

| Característica | Cómo aparece | Qué obliga a hacer al scraper |
|---|---|---|
| Paginación | 8 resultados por página y enlace "Siguiente" | Recorrer páginas hasta el final |
| Duplicados | El último resultado de una página se repite al inicio de la siguiente | Deduplicar por `data-id` |
| Formatos de precio | `COP 118.700 / día`, `$ 149,600 diarios`, `119600 pesos por día`, `Total 3 días: COP 375.600` | Distinguir precio por día y precio total, y los separadores `.` y `,` |
| Formatos de fecha | `16/10/2026 → 19/10/2026` y `del 2026-10-16 al 2026-10-19` | Normalizar y verificar contra la búsqueda |
| Campos faltantes | Transmisión (~10 %) y puestos (~12 %) | Completarlos en la normalización (tarea 2.9) |
| Latencia | 50–600 ms por respuesta | — |
| Fallos transitorios | `500`/`503` (`MOCK_CARS_FAILURE_RATE`) | Reintentos de Prefect |
| Bloqueos | `429` ocasional | **No** se reintenta (política) |
| Timeouts | Respuestas de 30 s (`MOCK_CARS_SLOW_RATE`) | Abandonar y reintentar |

## Datos

- **Modelos y categorías reales** del mercado colombiano (Kia Picanto, Chevrolet Onix, Renault Duster, Toyota Fortuner, Hyundai H1, Mercedes-Benz Clase C…), con rangos de precio por día verosímiles.
- **Empresas ficticias** (Andes Rent a Car, Caribe Wheels, Ruta Verde Autos, Montaña Car Rental, Pacífico Drive), para no atribuir precios inventados a marcas reales. Cada página muestra el aviso "Fuente SIMULADA".
- **Determinista:** la misma ciudad y fechas producen siempre los mismos vehículos (IDs estables, como una fuente real). El precio varía ±4 % cada día, para que la ingesta registre actualizaciones.

## Verificación (2026-10-09)

- **10 pruebas sin red** (64 en total en el pipeline): los cuatro formatos de precio, los dos de fecha, la paginación con duplicado y el error transitorio.
- **En vivo** desde el worker: CTG 23→26 oct, 3 páginas, 18 autos, 0 descartes.
