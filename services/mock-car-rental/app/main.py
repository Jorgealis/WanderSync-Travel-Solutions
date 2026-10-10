"""RutaFácil (SIMULADO) — fuente de alquiler de autos para WanderSync.

Decisión de la tarea 2.7: ninguna fuente real de autos es viable sin incumplir la
política de scraping, y el enunciado (sección 3.1) permite servicios mockeados "que
simulen la complejidad de dichas fuentes". Este servicio la simula:

- HTML con resultados paginados (MOCK_CARS_PAGE_SIZE por página) y enlace "Siguiente";
- formatos de precio y de fecha distintos según la empresa;
- campos faltantes (puestos, transmisión) y un resultado repetido entre páginas;
- latencia aleatoria, errores 500/503/429 y respuestas lentas (provocan timeout).

    GET /alquiler/{CIUDAD}?recogida=AAAA-MM-DD&devolucion=AAAA-MM-DD&pagina=N
"""

import asyncio
import html
import os
import random
from datetime import date

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.catalog import CITIES, format_dates, format_price, vehicles_for

SEED = int(os.environ.get("MOCK_CARS_SEED", "42"))
PAGE_SIZE = int(os.environ.get("MOCK_CARS_PAGE_SIZE", "8"))
FAILURE_RATE = float(os.environ.get("MOCK_CARS_FAILURE_RATE", "0.1"))
SLOW_RATE = float(os.environ.get("MOCK_CARS_SLOW_RATE", "0.03"))
SLOW_SECONDS = float(os.environ.get("MOCK_CARS_SLOW_SECONDS", "30"))
LATENCY_MS = (int(os.environ.get("MOCK_CARS_LATENCY_MS_MIN", "50")), int(os.environ.get("MOCK_CARS_LATENCY_MS_MAX", "600")))

app = FastAPI(title="RutaFácil (simulado)", docs_url=None, redoc_url=None, openapi_url=None)
_chaos = random.Random()

BANNER = (
    '<p class="aviso">Fuente SIMULADA para el proyecto académico WanderSync: '
    "empresas y precios ficticios.</p>"
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    return "User-agent: *\nAllow: /alquiler/\n"


@app.get("/alquiler/{city}", response_class=HTMLResponse)
async def search(
    city: str,
    recogida: date = Query(...),
    devolucion: date = Query(...),
    pagina: int = Query(1, ge=1),
) -> HTMLResponse:
    await asyncio.sleep(_chaos.uniform(*LATENCY_MS) / 1000)
    roll = _chaos.random()
    if roll < SLOW_RATE:
        await asyncio.sleep(SLOW_SECONDS)  # el cliente debería abandonar por timeout
    elif roll < SLOW_RATE + FAILURE_RATE:
        # Sobre todo 500/503 (transitorios: se reintentan); 429 es raro (bloqueo: no se reintenta).
        status = _chaos.choice([500, 503, 500, 503, 429])
        return HTMLResponse(f"<h1>Error {status}</h1><p>Inténtalo más tarde.</p>", status_code=status)

    city = city.upper()
    if city not in CITIES or devolucion <= recogida:
        return HTMLResponse(f"<html><head><title>Sin resultados | RutaFácil</title></head><body>{BANNER}"
                            "<p class='sin-resultados'>Ciudad o fechas no disponibles.</p></body></html>",
                            status_code=404)

    vehicles = vehicles_for(city, recogida, devolucion, SEED, date.today())
    days = (devolucion - recogida).days
    start = (pagina - 1) * PAGE_SIZE
    page = vehicles[start:start + PAGE_SIZE]
    if pagina > 1 and page:
        page = [vehicles[start - 1], *page]  # el último de la página anterior se repite (duplicado)

    items = "\n".join(_item(v, recogida, devolucion, days) for v in page)
    has_next = start + PAGE_SIZE < len(vehicles)
    next_link = (
        f'<a class="siguiente" href="/alquiler/{city}?recogida={recogida}&amp;devolucion={devolucion}&amp;pagina={pagina + 1}">Siguiente</a>'
        if has_next else ""
    )
    body = (
        f"<html><head><title>Alquiler de carros en {html.escape(CITIES[city])} | RutaFácil (simulado)</title></head>"
        f"<body>{BANNER}<p class='total'>{len(vehicles)} vehículos disponibles</p>"
        f"<ul class='resultados'>\n{items}\n</ul><nav>{next_link}</nav></body></html>"
    )
    return HTMLResponse(body)


def _item(vehicle, pickup: date, dropoff: date, days: int) -> str:
    seats = f'<span class="puestos">{vehicle.seats} puestos</span>' if vehicle.seats else ""
    transmission = vehicle.transmission or "—"
    return (
        f'<li class="vehiculo" data-id="{vehicle.vehicle_id}">'
        f'<h3 class="modelo">{html.escape(vehicle.model)} <small>o similar</small></h3>'
        f'<span class="empresa">{html.escape(vehicle.company)}</span>'
        f'<span class="categoria">{html.escape(vehicle.category)}</span>'
        f'<span class="transmision">{transmission}</span>{seats}'
        f'<span class="precio">{html.escape(format_price(vehicle, days))}</span>'
        f'<span class="fechas">{html.escape(format_dates(vehicle, pickup, dropoff))}</span>'
        "</li>"
    )
