"""Normalización y validación de registros extraídos → filas del catálogo (tarea 2.9).

Funciones puras (sin red ni BD) para que sean fáciles de probar y de paralelizar:
el flow las ejecuta con dask.bag sobre el clúster (ver flows/ingest.py).

Cada función devuelve ("ok", fila) o ("discarded", motivo). Reglas:
- precios a USD con las tasas del día (el original se conserva en price_original);
- rangos razonables: un precio fuera de rango es casi siempre un error de la fuente
  (p. ej. Hotelbeds publicó un hotel "desde 497.102 EUR" en su entorno de evaluación);
- campos faltantes de la fuente simulada de autos se completan con el valor típico
  de la categoría (y la fila lo indica en el resumen);
- inventario inicial: el cupo real si la fuente lo publica; si no, el valor por defecto.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ingestion.fx import FxRates, UnsupportedCurrency

# Rangos en USD considerados plausibles.
FLIGHT_PRICE_RANGE = (Decimal("10"), Decimal("3000"))  # por pasajero
HOTEL_NIGHT_RANGE = (Decimal("10"), Decimal("2000"))  # por habitación y noche
CAR_DAY_RANGE = (Decimal("5"), Decimal("1000"))  # por día

CAR_DEFAULT_TRANSMISSION = {"SUV": "AUTOMATIC", "LUXURY": "AUTOMATIC"}  # resto: MANUAL
CAR_DEFAULT_SEATS = {"VAN": 12}  # resto: 5


@dataclass(frozen=True)
class Defaults:
    seats: int = 30
    rooms: int = 10
    cars: int = 5


Result = tuple[str, Any]


def _in_range(value: Decimal, bounds: tuple[Decimal, Decimal]) -> bool:
    return bounds[0] <= value <= bounds[1]


def normalize_flight(record: Any, fx: FxRates, defaults: Defaults) -> Result:
    try:
        price = fx.to_usd(record.price_original, record.currency_original)
    except UnsupportedCurrency as exc:
        return "discarded", str(exc)
    if not _in_range(price, FLIGHT_PRICE_RANGE):
        return "discarded", f"precio fuera de rango: {price} USD ({record.airline} {record.origin}-{record.destination})"
    if record.arrival_at <= record.departure_at:
        return "discarded", "llegada no posterior a la salida"
    return "ok", {
        "source": record.source,
        "external_id": record.external_id,
        "airline": record.airline,
        "operated_by": record.operated_by,
        "flight_number": record.flight_number,
        "origin": record.origin,
        "destination": record.destination,
        "departure_at": record.departure_at,
        "arrival_at": record.arrival_at,
        "stops": record.stops,
        "cabin_class": record.cabin_class,
        "price": price,
        "currency": "USD",
        "price_original": record.price_original,
        "currency_original": record.currency_original,
        "seats_total": defaults.seats,
        "seats_available": defaults.seats,
        "scraped_at": record.scraped_at,
    }


def normalize_room(record: Any, fx: FxRates, defaults: Defaults) -> Result:
    try:
        total = fx.to_usd(record.price_original, record.currency_original)
    except UnsupportedCurrency as exc:
        return "discarded", str(exc)
    if record.nights <= 0:
        return "discarded", "estadía sin noches"
    per_night = (total / record.nights).quantize(Decimal("0.01"))
    if not _in_range(per_night, HOTEL_NIGHT_RANGE):
        return "discarded", f"precio por noche fuera de rango: {per_night} USD ({record.hotel_name})"
    rooms = record.allotment if record.allotment and record.allotment > 0 else defaults.rooms
    return "ok", {
        "source": record.source,
        "external_id": record.external_id,
        "hotel_code": record.hotel_code,
        "hotel_name": record.hotel_name[:150],
        "city_code": record.city_code,
        "zone_name": record.zone_name,
        "address": None,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "stars": record.stars,
        "category_name": record.category_name,
        "rating": None,
        "room_code": record.room_code,
        "room_name": record.room_name[:150],
        "room_type": record.room_type,
        "board_code": record.board_code,
        "board_name": record.board_name[:50],
        "max_guests": record.max_guests,
        "check_in": record.check_in,
        "check_out": record.check_out,
        "price_per_night": per_night,
        "price_total": total,
        "currency": "USD",
        "price_original": record.price_original,
        "currency_original": record.currency_original,
        "rooms_total": rooms,
        "rooms_available": rooms,
        "scraped_at": record.scraped_at,
    }


def normalize_car(record: Any, fx: FxRates, defaults: Defaults) -> Result:
    try:
        total = fx.to_usd(record.price_original, record.currency_original)
        per_day = fx.to_usd(record.price_per_day_original, record.currency_original)
    except UnsupportedCurrency as exc:
        return "discarded", str(exc)
    if not _in_range(per_day, CAR_DAY_RANGE):
        return "discarded", f"precio por día fuera de rango: {per_day} USD ({record.model})"
    return "ok", {
        "source": record.source,
        "external_id": record.external_id,
        "company": record.company,
        "model": record.model,
        "category": record.category,
        "transmission": record.transmission or CAR_DEFAULT_TRANSMISSION.get(record.category, "MANUAL"),
        "seats": record.seats or CAR_DEFAULT_SEATS.get(record.category, 5),
        "city_code": record.city_code,
        "pickup_date": record.pickup_date,
        "dropoff_date": record.dropoff_date,
        "price_per_day": per_day,
        "price_total": total,
        "currency": "USD",
        "price_original": record.price_original,
        "currency_original": record.currency_original,
        "units_total": defaults.cars,
        "units_available": defaults.cars,
        "scraped_at": record.scraped_at,
        "_filled": [field for field, value in (("transmission", record.transmission), ("seats", record.seats)) if value is None],
    }


NORMALIZERS = {"flights": normalize_flight, "hotels": normalize_room, "cars": normalize_car}


def split_results(results: Iterable[Result]) -> tuple[list[dict], list[str], int]:
    """Separa filas válidas y descartes, y deduplica por (source, external_id) con el precio menor.

    Devuelve (filas, motivos de descarte, campos completados).
    """
    rows: dict[tuple[str, str], dict] = {}
    discarded: list[str] = []
    filled = 0
    for status, value in results:
        if status != "ok":
            discarded.append(value)
            continue
        filled += len(value.pop("_filled", []))
        key = (value["source"], value["external_id"])
        price_key = "price" if "price" in value else "price_total"
        if key not in rows or value[price_key] < rows[key][price_key]:
            rows[key] = value
    return list(rows.values()), discarded, filled
