"""Fuente 2 — Hotelbeds (hoteles), API oficial. No es scraping de HTML.

Ficha de la fuente: docs/fuentes/hotelbeds.md. Puntos clave:
- autenticación: Api-key + X-Signature = SHA-256(key + secret + timestamp Unix);
- 50 peticiones por día (entorno de evaluación) → DailyQuota, compartida entre workers;
- una oferta = hotel + tipo de habitación + régimen + fechas, con la tarifa más barata;
- `allotment` (cupos reales) se usa como inventario inicial.

Uso manual (consume UNA petición de la cuota):

    python -m scrapers.hotelbeds MDE 2026-10-16 3
    python -m scrapers.hotelbeds MDE 2026-10-16 3 --save-fixture tests/fixtures/x.json
"""

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from scrapers.base import ParseError, PoliteClient, ScraperSettings
from scrapers.quota import DailyQuota

SOURCE = "hotelbeds"
AVAILABILITY_PATH = "/hotel-api/1.0/hotels"

ROOM_TYPES = {"SGL": "SINGLE", "DBL": "DOUBLE", "TWN": "TWIN", "SUI": "SUITE", "JSU": "SUITE", "FAM": "FAMILY"}
_STARS_IN_NAME = re.compile(r"(\d)\s*(?:STARS?|\*)", re.IGNORECASE)  # "5 STARS", "APARTHOTEL 3*"
_STARS_IN_CODE = re.compile(r"^(\d)(?:EST|LUX|LUJ|\*)", re.IGNORECASE)


@dataclass(frozen=True)
class HotelbedsSettings:
    api_key: str
    api_secret: str
    base_url: str = "https://api.test.hotelbeds.com"
    daily_budget: int = 45  # el límite real es 50: se deja margen para pruebas manuales
    min_delay_seconds: float = 1.0
    quota_dir: str = "/var/lib/wandersync/quota"

    @classmethod
    def from_env(cls) -> "HotelbedsSettings":
        env = os.environ
        key, secret = env.get("HOTELBEDS_API_KEY", "").strip(), env.get("HOTELBEDS_API_SECRET", "").strip()
        if not key or not secret:
            raise ValueError("Faltan HOTELBEDS_API_KEY / HOTELBEDS_API_SECRET en el entorno")
        return cls(
            api_key=key,
            api_secret=secret,
            base_url=(env.get("HOTELBEDS_BASE_URL") or cls.base_url).rstrip("/"),
            daily_budget=int(env.get("HOTELBEDS_DAILY_BUDGET", cls.daily_budget)),
            min_delay_seconds=float(env.get("HOTELBEDS_MIN_DELAY_SECONDS", cls.min_delay_seconds)),
            quota_dir=env.get("INGEST_STATE_DIR", "/var/lib/wandersync") + "/quota",
        )


@dataclass(frozen=True)
class HotelRecord:
    """Oferta de hotel tal como la publica la fuente (antes de normalizar a USD, tarea 2.9)."""

    source: str
    external_id: str
    hotel_code: str
    hotel_name: str
    city_code: str
    zone_name: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    stars: int | None
    category_name: str | None
    room_code: str
    room_name: str
    room_type: str
    board_code: str
    board_name: str
    max_guests: int
    check_in: date
    check_out: date
    nights: int
    price_original: Decimal  # total de la estadía por habitación
    currency_original: str
    allotment: int | None
    scraped_at: datetime


def signature(api_key: str, api_secret: str, timestamp: int) -> str:
    return hashlib.sha256(f"{api_key}{api_secret}{timestamp}".encode()).hexdigest()


def signed_headers(settings: HotelbedsSettings, timestamp: int | None = None) -> dict[str, str]:
    timestamp = int(time.time()) if timestamp is None else timestamp
    return {
        "Api-key": settings.api_key,
        "X-Signature": signature(settings.api_key, settings.api_secret, timestamp),
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
    }


def build_request(city_code: str, check_in: date, nights: int, adults: int = 2, rooms: int = 1) -> dict[str, Any]:
    return {
        "stay": {"checkIn": check_in.isoformat(), "checkOut": (check_in + timedelta(days=nights)).isoformat()},
        "occupancies": [{"rooms": rooms, "adults": adults, "children": 0}],
        "destination": {"code": city_code},
    }


def make_client(settings: HotelbedsSettings, scraper_settings: ScraperSettings | None = None, **kwargs: Any) -> PoliteClient:
    """PoliteClient con la pausa propia de Hotelbeds (una API tolera más ritmo que un sitio web)."""
    base = scraper_settings or ScraperSettings.from_env()
    return PoliteClient(replace(base, min_delay_seconds=settings.min_delay_seconds), **kwargs)


def fetch(
    client: PoliteClient,
    settings: HotelbedsSettings,
    quota: DailyQuota,
    city_code: str,
    check_in: date,
    nights: int,
) -> dict[str, Any]:
    """Una consulta de disponibilidad. Reserva cuota ANTES de enviar (la API cuenta también los fallos)."""
    quota.reserve()
    response = client.post(
        settings.base_url + AVAILABILITY_PATH,
        json=build_request(city_code, check_in, nights),
        headers=signed_headers(settings),
    )
    try:
        return response.json()
    except ValueError as exc:
        raise ParseError(f"La respuesta no es JSON: {response.text[:120]!r}") from exc


def parse(payload: dict[str, Any], scraped_at: datetime | None = None) -> list[HotelRecord]:
    records, _failures = parse_with_report(payload, scraped_at)
    return records


def parse_with_report(
    payload: dict[str, Any], scraped_at: datetime | None = None
) -> tuple[list[HotelRecord], list[str]]:
    """Convierte la respuesta de disponibilidad en ofertas: una por hotel + habitación + régimen,
    con la tarifa más barata. Devuelve también los motivos de las tarifas descartadas."""
    scraped_at = scraped_at or datetime.now(timezone.utc)
    hotels_block = payload.get("hotels")
    if not isinstance(hotels_block, dict):
        raise ParseError(f"Respuesta sin bloque 'hotels': claves {sorted(payload)[:5]}")
    check_in = _parse_date(hotels_block.get("checkIn"), "checkIn")
    check_out = _parse_date(hotels_block.get("checkOut"), "checkOut")
    nights = (check_out - check_in).days

    offers: dict[str, HotelRecord] = {}
    failures: list[str] = []
    for hotel in hotels_block.get("hotels", []):
        for room in hotel.get("rooms", []):
            for rate in room.get("rates", []):
                try:
                    record = _to_record(hotel, room, rate, check_in, check_out, nights, scraped_at)
                except (ParseError, KeyError, TypeError) as exc:
                    failures.append(f"hotel {hotel.get('code')} habitación {room.get('code')}: {exc}")
                    continue
                previous = offers.get(record.external_id)
                if previous is None or record.price_original < previous.price_original:
                    offers[record.external_id] = record
    return list(offers.values()), failures


def _to_record(
    hotel: dict, room: dict, rate: dict, check_in: date, check_out: date, nights: int, scraped_at: datetime
) -> HotelRecord:
    net = _decimal(rate.get("net"))
    if net is None or net <= 0:
        raise ParseError(f"tarifa neta inválida {rate.get('net')!r}")
    room_code = str(room["code"])
    board_code = str(rate["boardCode"])
    hotel_code = str(hotel["code"])
    allotment = rate.get("allotment")
    return HotelRecord(
        source=SOURCE,
        external_id=f"{hotel_code}:{room_code}:{board_code}:{check_in.isoformat()}:{check_out.isoformat()}",
        hotel_code=hotel_code,
        hotel_name=str(hotel["name"]).strip(),
        city_code=str(hotel["destinationCode"]),
        zone_name=hotel.get("zoneName"),
        latitude=_decimal(hotel.get("latitude"), places=6),
        longitude=_decimal(hotel.get("longitude"), places=6),
        stars=parse_stars(hotel.get("categoryCode"), hotel.get("categoryName")),
        category_name=hotel.get("categoryName"),
        room_code=room_code,
        room_name=str(room.get("name") or room_code).strip(),
        room_type=ROOM_TYPES.get(room_code.split(".")[0].upper(), "OTHER"),
        board_code=board_code,
        board_name=str(rate.get("boardName") or board_code),
        max_guests=int(rate.get("adults") or 1) + int(rate.get("children") or 0),
        check_in=check_in,
        check_out=check_out,
        nights=nights,
        price_original=net,
        currency_original=str(hotel.get("currency") or "EUR"),
        allotment=int(allotment) if allotment is not None else None,
        scraped_at=scraped_at,
    )


def parse_stars(category_code: str | None, category_name: str | None) -> int | None:
    """"5 STARS"/"5EST" → 5. Las categorías que no son de estrellas (hostales, apartamentos) → None."""
    for pattern, value in ((_STARS_IN_NAME, category_name), (_STARS_IN_CODE, category_code)):
        match = pattern.search(value or "")
        if match and 1 <= int(match.group(1)) <= 5:
            return int(match.group(1))
    return None


def _parse_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ParseError(f"Fecha '{field}' inválida: {value!r}") from exc


def _decimal(value: Any, places: int | None = None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return round(number, places) if places is not None else number


def make_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    """Respuesta real reducida a los campos que usa el parser (sin rateKey, políticas, etc.)."""
    hotel_fields = ("code", "name", "categoryCode", "categoryName", "destinationCode", "zoneName",
                    "latitude", "longitude", "currency", "minRate", "maxRate")
    rate_fields = ("net", "boardCode", "boardName", "adults", "children", "allotment")
    block = payload["hotels"]
    return {"hotels": {
        "checkIn": block.get("checkIn"),
        "checkOut": block.get("checkOut"),
        "total": block.get("total"),
        "hotels": [
            {**{k: h.get(k) for k in hotel_fields},
             "rooms": [{"code": r.get("code"), "name": r.get("name"),
                        "rates": [{k: rt.get(k) for k in rate_fields} for rt in r.get("rates", [])]}
                       for r in h.get("rooms", [])]}
            for h in block.get("hotels", [])
        ],
    }}


def main() -> None:
    parser = argparse.ArgumentParser(description="Hotelbeds: disponibilidad de una ciudad (1 petición)")
    parser.add_argument("city")
    parser.add_argument("check_in", type=date.fromisoformat)
    parser.add_argument("nights", type=int)
    parser.add_argument("--save-fixture", metavar="PATH")
    args = parser.parse_args()

    settings = HotelbedsSettings.from_env()
    quota = DailyQuota(settings.quota_dir, SOURCE, settings.daily_budget)
    with make_client(settings) as client:
        payload = fetch(client, settings, quota, args.city, args.check_in, args.nights)
    records, failures = parse_with_report(payload)

    hotels = {r.hotel_code for r in records}
    print(f"{len(hotels)} hoteles, {len(records)} ofertas (habitación + régimen), {len(failures)} tarifas descartadas "
          f"| cuota usada hoy: {quota.used()}/{settings.daily_budget}")
    for r in sorted(records, key=lambda r: r.price_original)[:12]:
        stars = f"{r.stars}*" if r.stars else (r.category_name or "-")
        print(f"  {r.price_original:>10} {r.currency_original} {stars:>4} {r.hotel_name[:38]:38} | {r.room_name[:24]:24} | "
              f"{r.board_name[:18]:18} | cupos {r.allotment}")
    if args.save_fixture:
        with open(args.save_fixture, "w", encoding="utf-8") as fh:
            json.dump(make_fixture(payload), fh, ensure_ascii=False, indent=1)
        print(f"Fixture guardado en {args.save_fixture}")


if __name__ == "__main__":
    main()
