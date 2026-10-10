"""Pruebas de normalización (2.9) con registros reales de los fixtures y casos límite."""

import json
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx

from ingestion.fx import FxRates, fetch_rates
from ingestion.normalize import Defaults, normalize_car, normalize_flight, normalize_room, split_results
from scrapers import google_flights, hotelbeds, mock_car_rental

FIXTURES = Path(__file__).parent / "fixtures"
FX = FxRates(cop_per_usd=Decimal("3200"), usd_per_eur=Decimal("1.12"), source="test", as_of="2026-10-09")
DEFAULTS = Defaults(seats=30, rooms=10, cars=5)


def flights():
    page = (FIXTURES / "google_flights_bog_mde_2026-10-16.html").read_text(encoding="utf-8")
    return google_flights.parse(page, "BOG", "MDE", date(2026, 10, 16))


def rooms():
    return hotelbeds.parse(json.loads((FIXTURES / "hotelbeds_ctg_2026-10-16_3n.json").read_text(encoding="utf-8")))


def cars():
    records = []
    for n in (1, 2):
        page = (FIXTURES / f"mock_cars_mde_2026-10-16_p{n}.html").read_text(encoding="utf-8")
        records += mock_car_rental.parse_page(page, "MDE", date(2026, 10, 16), date(2026, 10, 19))[0]
    return records


def test_flights_converted_to_usd_with_default_inventory():
    rows, discarded, _ = split_results(normalize_flight(r, FX, DEFAULTS) for r in flights())
    assert len(rows) == 50 and discarded == []
    for row in rows:
        assert row["currency"] == "USD" and row["currency_original"] == "COP"
        assert row["price"] == FX.to_usd(row["price_original"], "COP")
        assert row["seats_total"] == row["seats_available"] == 30


def test_hotels_use_real_allotment_and_price_per_night():
    rows, discarded, _ = split_results(normalize_room(r, FX, DEFAULTS) for r in rooms())
    # La respuesta real de Hotelbeds trae 4 tarifas absurdas (p. ej. 303.746 USD/noche en
    # "Hotel Dorado Plaza"): el filtro de rango las descarta.
    assert len(discarded) == 4 and all("fuera de rango" in d for d in discarded)
    assert len(rows) == 326 - 4
    playa_norte = next(r for r in rows if r["hotel_name"] == "Hotel Playa Norte" and r["room_name"] == "Double standard"
                       and r["board_name"] == "ROOM ONLY")
    assert playa_norte["price_total"] == Decimal("103.89")  # 92.76 EUR × 1.12
    assert playa_norte["price_per_night"] == Decimal("34.63")
    assert playa_norte["rooms_total"] == playa_norte["rooms_available"] == 13  # allotment real


def test_hotel_price_outlier_is_discarded():
    # Caso real de Hotelbeds: "Hotel 47 Medellin street ... desde 497102.12 EUR".
    outlier = replace(rooms()[0], price_original=Decimal("497102.12"))
    status, reason = normalize_room(outlier, FX, DEFAULTS)
    assert status == "discarded" and "fuera de rango" in reason


def test_cars_fill_missing_fields_by_category():
    rows, discarded, filled = split_results(normalize_car(r, FX, DEFAULTS) for r in cars())
    assert discarded == [] and len(rows) == 15
    assert filled >= 1  # el fixture tiene transmisiones faltantes
    for row in rows:
        assert row["transmission"] in {"MANUAL", "AUTOMATIC"}
        assert row["seats"] > 0
        assert row["units_total"] == 5
        assert row["price_total"] == FX.to_usd(row["price_original"], "COP")
        assert row["price_total"] == (row["price_original"] / Decimal("3200")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_missing_transmission_defaults():
    car = cars()[0]
    suv = replace(car, category="SUV", transmission=None, seats=None)
    van = replace(car, category="VAN", transmission=None, seats=None)
    assert normalize_car(suv, FX, DEFAULTS)[1]["transmission"] == "AUTOMATIC"
    assert normalize_car(van, FX, DEFAULTS)[1]["seats"] == 12


def test_unsupported_currency_is_discarded():
    status, reason = normalize_flight(replace(flights()[0], currency_original="GBP"), FX, DEFAULTS)
    assert status == "discarded" and "GBP" in reason


def test_dedup_keeps_cheapest():
    base = flights()[0]
    cheap = replace(base, price_original=Decimal("100000"))
    expensive = replace(base, price_original=Decimal("300000"))
    rows, _, _ = split_results([normalize_flight(expensive, FX, DEFAULTS), normalize_flight(cheap, FX, DEFAULTS)])
    assert len(rows) == 1 and rows[0]["price_original"] == Decimal("100000")


def test_fetch_rates_from_public_sources():
    def handler(request):
        if "datos.gov.co" in request.url.host:
            return httpx.Response(200, json=[{"valor": "3194.44", "vigenciadesde": "2026-10-10T00:00:00.000"}])
        return httpx.Response(200, json={"date": "2026-10-09", "rates": {"USD": 1.1206}})

    rates = fetch_rates(httpx.Client(transport=httpx.MockTransport(handler)))
    assert (rates.cop_per_usd, rates.usd_per_eur, rates.source) == (Decimal("3194.44"), Decimal("1.1206"), "trm+ecb")


def test_fetch_rates_falls_back_per_source(monkeypatch):
    monkeypatch.setenv("FX_COP_PER_USD", "4000")

    def handler(request):
        if "datos.gov.co" in request.url.host:
            return httpx.Response(503)
        return httpx.Response(200, json={"date": "2026-10-09", "rates": {"USD": 1.1}})

    rates = fetch_rates(httpx.Client(transport=httpx.MockTransport(handler)))
    assert rates.cop_per_usd == Decimal("4000") and rates.usd_per_eur == Decimal("1.1")
    assert rates.source == "fallback-cop+ecb"
