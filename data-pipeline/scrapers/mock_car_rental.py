"""Fuente 3 — RutaFácil (SIMULADA), alquiler de autos.

Decisión de la tarea 2.7 (PROGRESO.md §1.4): ninguna fuente real de autos es viable sin
incumplir la política de scraping; el enunciado (3.1) permite servicios mockeados que
simulen la complejidad de las fuentes reales. Este scraper la trata EXACTAMENTE como a una
fuente real: HTML paginado, PoliteClient, misma clasificación de errores.

Complejidad que resuelve:
- paginación con enlace "Siguiente" y un resultado repetido entre páginas;
- cuatro formatos de precio (por día o total; "COP 118.700", "$ 149,600", "119600 pesos");
- dos formatos de fecha ("16/10/2026 → 19/10/2026" y "del 2026-10-16 al 2026-10-19");
- transmisión o puestos faltantes (se completan en la normalización, tarea 2.9).

Uso manual:
    python -m scrapers.mock_car_rental MDE 2026-10-16 2026-10-19
"""

import argparse
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from selectolax.parser import HTMLParser

from scrapers.base import ParseError, PoliteClient, ScraperSettings

SOURCE = "wandersync-mock-cars"
CATEGORIES = {"Económico": "ECONOMY", "Compacto": "COMPACT", "SUV / Camioneta": "SUV", "Van": "VAN", "Lujo": "LUXURY"}
TRANSMISSIONS = {"Manual": "MANUAL", "Automática": "AUTOMATIC"}

_TOTAL_PRICE = re.compile(r"^Total (?P<days>\d+) días?: COP (?P<amount>[\d.]+)$")
_DAILY_PRICE = re.compile(r"^(?:COP |\$ )?(?P<amount>\d[\d.,]*)(?: / día| diarios| pesos por día)$")
_DATES_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) → (\d{2})/(\d{2})/(\d{4})$")
_DATES_ISO = re.compile(r"^del (\d{4}-\d{2}-\d{2}) al (\d{4}-\d{2}-\d{2})$")
_SEATS = re.compile(r"^(\d+) puestos$")


@dataclass(frozen=True)
class CarRecord:
    """Oferta tal como la publica la fuente (antes de normalizar a USD y completar faltantes, 2.9)."""

    source: str
    external_id: str
    company: str
    model: str
    category: str
    transmission: str | None  # None = la fuente no lo publicó
    seats: int | None
    city_code: str
    pickup_date: date
    dropoff_date: date
    days: int
    price_per_day_original: Decimal
    price_original: Decimal  # total del alquiler
    currency_original: str
    scraped_at: datetime


def base_url() -> str:
    return os.environ.get("MOCK_CARS_URL", "http://mock-car-rental:8000").rstrip("/")


def fetch_page(client: PoliteClient, url: str, city: str, pickup: date, dropoff: date, page: int) -> str:
    params = {"recogida": pickup.isoformat(), "devolucion": dropoff.isoformat(), "pagina": str(page)}
    return client.get(f"{url}/alquiler/{city}", params=params).text


def parse_page(
    page_html: str, city: str, pickup: date, dropoff: date, scraped_at: datetime | None = None
) -> tuple[list[CarRecord], list[str], bool]:
    """Devuelve (ofertas, motivos de descarte, ¿hay página siguiente?)."""
    scraped_at = scraped_at or datetime.now(timezone.utc)
    tree = HTMLParser(page_html)
    items = tree.css("li.vehiculo")
    if not items and tree.css_first("ul.resultados") is None:
        raise ParseError("La página no tiene la lista de resultados (ul.resultados): ¿cambió el formato?")

    records, failures = [], []
    for item in items:
        try:
            records.append(_parse_item(item, city, pickup, dropoff, scraped_at))
        except ParseError as exc:
            failures.append(f"{item.attributes.get('data-id')}: {exc}")
    return records, failures, tree.css_first("a.siguiente") is not None


def fetch_all(
    client: PoliteClient, url: str, city: str, pickup: date, dropoff: date, max_pages: int = 10
) -> tuple[list[CarRecord], list[str], int]:
    """Recorre todas las páginas. Devuelve (ofertas sin duplicados, descartes, páginas leídas)."""
    offers: dict[str, CarRecord] = {}
    failures: list[str] = []
    page = 1
    while page <= max_pages:
        records, page_failures, has_next = parse_page(fetch_page(client, url, city, pickup, dropoff, page), city, pickup, dropoff)
        failures += page_failures
        for record in records:
            offers.setdefault(record.external_id, record)  # el repetido entre páginas se ignora
        if not has_next:
            break
        page += 1
    return list(offers.values()), failures, page


def _text(item, selector: str) -> str | None:
    node = item.css_first(selector)
    return node.text(strip=True) if node else None


def _parse_item(item, city: str, pickup: date, dropoff: date, scraped_at: datetime) -> CarRecord:
    vehicle_id = item.attributes.get("data-id")
    model_node = item.css_first("h3.modelo")
    if not vehicle_id or model_node is None:
        raise ParseError("sin identificador o modelo")
    model = re.sub(r"\s*o similar$", "", model_node.text(separator=" ", strip=True))

    category_text = _text(item, ".categoria")
    category = CATEGORIES.get(category_text or "")
    if category is None:
        raise ParseError(f"categoría desconocida {category_text!r}")

    days = (dropoff - pickup).days
    published_pickup, published_dropoff = _parse_dates(_text(item, ".fechas") or "")
    if (published_pickup, published_dropoff) != (pickup, dropoff):
        raise ParseError(f"fechas publicadas {published_pickup}→{published_dropoff} no coinciden con la búsqueda")

    per_day, total = _parse_price(_text(item, ".precio") or "", days)
    seats_text = _text(item, ".puestos")
    seats_match = _SEATS.match(seats_text or "")

    return CarRecord(
        source=SOURCE,
        external_id=vehicle_id,
        company=_text(item, ".empresa") or "",
        model=model,
        category=category,
        transmission=TRANSMISSIONS.get(_text(item, ".transmision") or ""),
        seats=int(seats_match.group(1)) if seats_match else None,
        city_code=city,
        pickup_date=pickup,
        dropoff_date=dropoff,
        days=days,
        price_per_day_original=per_day,
        price_original=total,
        currency_original="COP",
        scraped_at=scraped_at,
    )


def _parse_price(text: str, days: int) -> tuple[Decimal, Decimal]:
    """(precio por día, total) en COP a partir de cualquiera de los cuatro formatos."""
    if match := _TOTAL_PRICE.match(text):
        if int(match["days"]) != days:
            raise ParseError(f"el total es de {match['days']} días y la búsqueda de {days}")
        total = Decimal(match["amount"].replace(".", ""))
        return (total / days).quantize(Decimal("0.01")), total
    if match := _DAILY_PRICE.match(text):
        per_day = Decimal(re.sub(r"[.,]", "", match["amount"]))  # COP no usa decimales
        return per_day, per_day * days
    raise ParseError(f"formato de precio desconocido {text!r}")


def _parse_dates(text: str) -> tuple[date, date]:
    if match := _DATES_SLASH.match(text):
        d1, m1, y1, d2, m2, y2 = (int(x) for x in match.groups())
        return date(y1, m1, d1), date(y2, m2, d2)
    if match := _DATES_ISO.match(text):
        return date.fromisoformat(match[1]), date.fromisoformat(match[2])
    raise ParseError(f"formato de fecha desconocido {text!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RutaFácil (simulado): todas las páginas de una búsqueda")
    parser.add_argument("city")
    parser.add_argument("pickup", type=date.fromisoformat)
    parser.add_argument("dropoff", type=date.fromisoformat)
    args = parser.parse_args()
    with PoliteClient(ScraperSettings.from_env()) as client:
        records, failures, pages = fetch_all(client, base_url(), args.city, args.pickup, args.dropoff)
    print(f"{len(records)} autos en {pages} páginas, {len(failures)} descartes")
    for r in sorted(records, key=lambda r: r.price_per_day_original)[:10]:
        print(f"  {r.price_per_day_original:>10} COP/día  {r.category:8} {r.model:24} {r.company:20} "
              f"{r.transmission or '¿?':9} {r.seats or '¿?'}")


if __name__ == "__main__":
    main()
