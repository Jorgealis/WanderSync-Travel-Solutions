"""Fuente 1 — Google Flights (vuelos solo ida por ruta y fecha).

Evaluación de la fuente (PROGRESO.md §1.4): robots.txt permite /travel/flights?q=...
y los resultados vienen renderizados en el HTML, sin ejecutar JavaScript. Cada vuelo
trae una etiqueta de accesibilidad (aria-label) con todos sus datos, por ejemplo:

    A partir de 515270 pesos colombianos. Vuelo con 1 escala de Avianca. Sale de
    Aeropuerto Internacional Alfonso Bonilla Aragón el viernes, octubre 16 a las 5:55.
    Llega a ... el viernes, octubre 16 a las 9:50. Duración total: 3 h 55 min. ...

El parser lee esas etiquetas: son texto para lectores de pantalla, mucho más estable
que las clases CSS ofuscadas de la página.

Uso manual (una sola petición):

    python -m scrapers.google_flights BOG MDE 2026-10-16
    python -m scrapers.google_flights BOG MDE 2026-10-16 --save-fixture tests/fixtures/x.html
"""

import argparse
import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from selectolax.parser import HTMLParser

from scrapers.base import ParseError, PoliteClient, ScraperSettings

SOURCE = "google-flights"
BASE_URL = "https://www.google.com/travel/flights"
CABIN_CLASS = "ECONOMY"  # la búsqueda por defecto de Google Flights es en clase económica

# Colombia no tiene horario de verano: todos sus aeropuertos están en UTC-5.
# Google muestra la hora LOCAL de cada aeropuerto, por eso hace falta la zona horaria.
COLOMBIA_TZ = timezone(timedelta(hours=-5), name="America/Bogota")
AIRPORT_TZ = {
    code: COLOMBIA_TZ
    for code in ("BOG", "MDE", "CTG", "CLO", "SMR", "ADZ", "BAQ", "BGA", "PEI", "CUC", "EOH")
}

CURRENCIES = {"pesos colombianos": "COP", "dólares estadounidenses": "USD"}
MONTHS = {
    name: number
    for number, names in enumerate(
        [("enero",), ("febrero",), ("marzo",), ("abril",), ("mayo",), ("junio",), ("julio",),
         ("agosto",), ("septiembre", "setiembre"), ("octubre",), ("noviembre",), ("diciembre",)],
        start=1,
    )
    for name in names
}

LABEL_PREFIXES = ("A partir de ", "Desde ")
_PRICE = re.compile(r"^(?:A partir de|Desde) (?P<amount>[\d.,\s]+?) (?P<currency>[a-záéíóúñ ]+?)[.(]")
_CARRIER = re.compile(
    r"Vuelo (?:directo|con (?P<stops>\d+) escalas?) de (?P<airline>.+?)\.(?=\s|$)"
)
_OPERATED = re.compile(r"Operado por (?P<operators>.+?)\.(?=\s|$)")
_MOMENT = r"el \w+, (?P<{p}month>[a-záéíóú]+) (?P<{p}day>\d{{1,2}}) a las (?P<{p}time>\d{{1,2}}:\d{{2}})"
_DEPARTURE = re.compile(r"Sale de .+? " + _MOMENT.format(p="d_"))
_ARRIVAL = re.compile(r"Llega a .+? " + _MOMENT.format(p="a_"))
_DURATION = re.compile(r"Duración total: (?:(?P<hours>\d+) h)?\s*(?:(?P<minutes>\d+) min)?")
_RESULTS_TITLE = re.compile(r"^De .+ a .+ \| Google")


@dataclass(frozen=True)
class FlightRecord:
    """Vuelo extraído tal como lo publica la fuente (antes de normalizar a USD, tarea 2.9)."""

    source: str
    external_id: str
    airline: str
    operated_by: str | None
    flight_number: str | None
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    stops: int
    cabin_class: str
    price_original: Decimal
    currency_original: str
    scraped_at: datetime


def build_params(origin: str, destination: str, departure_date: date) -> dict[str, str]:
    """Parámetros de búsqueda: solo ida, en español, precios en COP, mercado Colombia."""
    return {
        "q": f"Flights from {origin} to {destination} on {departure_date:%Y-%m-%d} one way",
        "hl": "es",
        "curr": "COP",
        "gl": "CO",
    }


def fetch(client: PoliteClient, origin: str, destination: str, departure_date: date) -> str:
    response = client.get(BASE_URL, params=build_params(origin, destination, departure_date))
    return response.text


def extract_labels(page_html: str) -> list[str]:
    """Etiquetas aria-label de los resultados, sin duplicados y en orden de aparición."""
    labels = (
        node.attributes.get("aria-label") or ""
        for node in HTMLParser(page_html).css("[aria-label]")
    )
    return list(dict.fromkeys(label for label in labels if label.startswith(LABEL_PREFIXES)))


def page_title(page_html: str) -> str:
    title = HTMLParser(page_html).css_first("title")
    return html.unescape(title.text()) if title else ""


def parse(
    page_html: str,
    origin: str,
    destination: str,
    departure_date: date,
    scraped_at: datetime | None = None,
) -> list[FlightRecord]:
    """Convierte la página de resultados en registros de vuelo.

    Lanza ParseError si la página no parece de resultados o si NINGUNA etiqueta se
    pudo interpretar (síntoma de que Google cambió el formato). Las etiquetas sueltas
    que no se entienden se omiten.
    """
    records, _failures = parse_with_report(page_html, origin, destination, departure_date, scraped_at)
    return records


def parse_with_report(
    page_html: str,
    origin: str,
    destination: str,
    departure_date: date,
    scraped_at: datetime | None = None,
) -> tuple[list[FlightRecord], list[str]]:
    """Igual que `parse`, pero devuelve también el motivo de cada etiqueta descartada."""
    scraped_at = scraped_at or datetime.now(timezone.utc)
    labels = extract_labels(page_html)
    if not labels:
        if _RESULTS_TITLE.match(page_title(page_html)):
            return [], []  # página de resultados válida, pero sin vuelos ese día
        raise ParseError(f"No es una página de resultados de vuelos (título: {page_title(page_html)!r})")

    records: dict[str, FlightRecord] = {}
    failures: list[str] = []
    for label in labels:
        try:
            record = parse_label(label, origin, destination, departure_date, scraped_at)
        except ParseError as exc:
            failures.append(str(exc))
            continue
        # Un mismo vuelo puede aparecer en "Mejores vuelos" y en "Otros vuelos".
        previous = records.get(record.external_id)
        if previous is None or record.price_original < previous.price_original:
            records[record.external_id] = record

    if not records:
        raise ParseError(f"Ninguna de las {len(labels)} etiquetas se pudo interpretar: {failures[:3]}")
    return list(records.values()), failures


def parse_label(
    label: str, origin: str, destination: str, departure_date: date, scraped_at: datetime
) -> FlightRecord:
    price = _search(_PRICE, label, "precio")
    carrier = _search(_CARRIER, label, "aerolínea")
    departure = _search(_DEPARTURE, label, "salida")
    arrival = _search(_ARRIVAL, label, "llegada")
    duration = _search(_DURATION, label, "duración")

    currency = CURRENCIES.get(price["currency"].strip())
    if currency is None:
        raise ParseError(f"Moneda desconocida: {price['currency']!r}")
    amount = Decimal(re.sub(r"\D", "", price["amount"]))
    if amount <= 0:
        raise ParseError(f"Precio inválido: {price['amount']!r}")

    departure_at = _to_datetime(departure, "d_", departure_date, AIRPORT_TZ.get(origin, COLOMBIA_TZ))
    arrival_at = _to_datetime(arrival, "a_", departure_at.date(), AIRPORT_TZ.get(destination, COLOMBIA_TZ))
    if arrival_at <= departure_at:
        raise ParseError(f"Llegada {arrival_at} no es posterior a la salida {departure_at}")

    airline = carrier["airline"].strip()
    operated = _OPERATED.search(label)
    operated_by = None
    if operated:
        # "Latam Airlines Colombia, Latam Airlines Colombia" = un operador por tramo.
        operators = list(dict.fromkeys(op.strip() for op in operated["operators"].split(",")))
        operated_by = ", ".join(operators)

    return FlightRecord(
        source=SOURCE,
        external_id=_external_id(airline, origin, destination, departure_at, arrival_at),
        airline=airline,
        operated_by=operated_by,
        flight_number=None,  # Google Flights no lo incluye en la etiqueta
        origin=origin,
        destination=destination,
        departure_at=departure_at,
        arrival_at=arrival_at,
        duration_minutes=int(duration["hours"] or 0) * 60 + int(duration["minutes"] or 0),
        stops=int(carrier["stops"] or 0),
        cabin_class=CABIN_CLASS,
        price_original=amount,
        currency_original=currency,
        scraped_at=scraped_at,
    )


def _search(pattern: re.Pattern[str], label: str, field: str) -> re.Match[str]:
    match = pattern.search(label)
    if match is None:
        raise ParseError(f"Campo '{field}' no encontrado en: {label[:120]!r}")
    return match


def _to_datetime(match: re.Match[str], prefix: str, reference: date, tz: timezone) -> datetime:
    """La etiqueta trae mes y día pero no año: se toma el año de la fecha de referencia,
    pasando al siguiente si el mes "da la vuelta" (búsqueda en diciembre, vuelo en enero)."""
    month_name = match[f"{prefix}month"]
    month = MONTHS.get(month_name)
    if month is None:
        raise ParseError(f"Mes desconocido: {month_name!r}")
    year = reference.year + (1 if month < reference.month else 0)
    hours, minutes = (int(part) for part in match[f"{prefix}time"].split(":"))
    return datetime(year, month, int(match[f"{prefix}day"]), hours, minutes, tzinfo=tz)


def _external_id(
    airline: str, origin: str, destination: str, departure_at: datetime, arrival_at: datetime
) -> str:
    """Google Flights no publica un ID: se deriva de los campos que identifican el vuelo
    (docs/contratos/modelo-datos.md). Si cambia el precio, el ID se mantiene."""
    key = "|".join(
        [airline, origin, destination, departure_at.isoformat(), arrival_at.isoformat(), CABIN_CLASS]
    )
    return hashlib.sha1(key.encode()).hexdigest()


def make_fixture(page_html: str) -> str:
    """HTML mínimo con el título y las etiquetas de resultados de una página real.

    Las pruebas usan esto en lugar de la página completa (~3,7 MB de HTML y JS de Google):
    conserva exactamente lo que lee el parser sin redistribuir la página entera.
    """
    items = "\n".join(
        f'  <li aria-label="{html.escape(label, quote=True)}"></li>' for label in extract_labels(page_html)
    )
    title = html.escape(page_title(page_html))
    return f"<!doctype html>\n<html><head><title>{title}</title></head>\n<body><ul>\n{items}\n</ul></body></html>\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper de Google Flights (una petición)")
    parser.add_argument("origin")
    parser.add_argument("destination")
    parser.add_argument("date", type=date.fromisoformat)
    parser.add_argument("--save-fixture", metavar="PATH")
    args = parser.parse_args()

    with PoliteClient(ScraperSettings.from_env()) as client:
        page_html = fetch(client, args.origin, args.destination, args.date)
    records = parse(page_html, args.origin, args.destination, args.date)

    print(f"{len(records)} vuelos {args.origin}->{args.destination} el {args.date}:")
    for r in sorted(records, key=lambda r: (r.price_original, r.departure_at)):
        operated = f" (opera {r.operated_by})" if r.operated_by else ""
        print(
            f"  {r.departure_at:%H:%M}->{r.arrival_at:%H:%M} {r.duration_minutes:>4} min "
            f"{r.stops} esc. {r.airline}{operated}: {r.price_original:,.0f} {r.currency_original}"
        )

    if args.save_fixture:
        with open(args.save_fixture, "w", encoding="utf-8") as fh:
            fh.write(make_fixture(page_html))
        print(f"Fixture guardado en {args.save_fixture}")
    if records:
        print("Ejemplo de registro:", {k: str(v) for k, v in asdict(records[0]).items()})


if __name__ == "__main__":
    main()
