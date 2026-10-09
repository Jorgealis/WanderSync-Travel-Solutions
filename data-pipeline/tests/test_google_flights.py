"""Pruebas del parser de Google Flights contra páginas reales guardadas (sin red).

Los fixtures se generaron el 2026-10-09 con:
    python -m scrapers.google_flights BOG MDE 2026-10-16 --save-fixture tests/fixtures/...
Si Google cambia el formato, regenerarlos y revisar qué prueba falla.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scrapers.base import ParseError
from scrapers.google_flights import SOURCE, build_params, make_fixture, parse, parse_label

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_DATE = date(2026, 10, 16)
COT = timezone(timedelta(hours=-5))
SCRAPED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bog_mde():
    return parse(load("google_flights_bog_mde_2026-10-16.html"), "BOG", "MDE", SEARCH_DATE, SCRAPED_AT)


@pytest.fixture(scope="module")
def clo_smr():
    return parse(load("google_flights_clo_smr_2026-10-16.html"), "CLO", "SMR", SEARCH_DATE, SCRAPED_AT)


def test_parses_every_result_of_real_pages(bog_mde, clo_smr):
    assert len(bog_mde) == 50
    assert len(clo_smr) == 6


def test_records_are_consistent(bog_mde, clo_smr):
    for record in bog_mde + clo_smr:
        assert record.source == SOURCE
        assert record.currency_original == "COP"
        assert record.price_original > 0
        assert record.arrival_at > record.departure_at
        assert record.departure_at.date() == SEARCH_DATE
        assert record.departure_at.utcoffset() == timedelta(hours=-5)
        assert record.stops >= 0
        assert record.flight_number is None
        assert len(record.external_id) == 40  # SHA-1 hex
        # En vuelos nacionales (misma zona horaria) la duración publicada cuadra con los horarios.
        assert record.duration_minutes == (record.arrival_at - record.departure_at).seconds // 60


def test_external_ids_are_unique(bog_mde):
    assert len({r.external_id for r in bog_mde}) == len(bog_mde)


def test_flight_with_layover_exact_values(clo_smr):
    flight = next(r for r in clo_smr if r.airline == "Avianca" and r.stops == 1)
    assert flight.origin == "CLO" and flight.destination == "SMR"
    assert flight.departure_at == datetime(2026, 10, 16, 5, 55, tzinfo=COT)
    assert flight.arrival_at == datetime(2026, 10, 16, 9, 50, tzinfo=COT)
    assert flight.duration_minutes == 3 * 60 + 55
    assert flight.price_original == Decimal("515270")


def test_operator_is_deduplicated_per_leg(clo_smr):
    # La fuente repite el operador por tramo: "Latam Airlines Colombia, Latam Airlines Colombia".
    latam = [r for r in clo_smr if r.operated_by and "Latam" in r.operated_by]
    assert latam and all(r.operated_by == "Latam Airlines Colombia" for r in latam)


def test_external_id_stable_when_price_changes():
    label = (
        "A partir de 204700 pesos colombianos. Vuelo directo de JetSMART. Sale de Aeropuerto X "
        "el viernes, octubre 16 a las 14:25. Llega a Aeropuerto Y el viernes, octubre 16 a las 15:31. "
        "Duración total: 1 h 6 min."
    )
    cheaper = label.replace("204700", "150000")
    a = parse_label(label, "BOG", "MDE", SEARCH_DATE, SCRAPED_AT)
    b = parse_label(cheaper, "BOG", "MDE", SEARCH_DATE, SCRAPED_AT)
    assert a.external_id == b.external_id
    assert b.price_original == Decimal("150000")


def test_arrival_next_day_and_year_rollover():
    label = (
        "A partir de 300000 pesos colombianos. Vuelo directo de Avianca. Sale de Aeropuerto X "
        "el jueves, diciembre 31 a las 23:30. Llega a Aeropuerto Y el viernes, enero 1 a las 0:40. "
        "Duración total: 1 h 10 min."
    )
    record = parse_label(label, "BOG", "CTG", date(2026, 12, 31), SCRAPED_AT)
    assert record.departure_at == datetime(2026, 12, 31, 23, 30, tzinfo=COT)
    assert record.arrival_at == datetime(2027, 1, 1, 0, 40, tzinfo=COT)


def test_duration_without_hours():
    label = (
        "Desde 99000 pesos colombianos. Vuelo directo de Clic. Sale de Aeropuerto X el viernes, "
        "octubre 16 a las 7:00. Llega a Aeropuerto Y el viernes, octubre 16 a las 7:45. "
        "Duración total: 45 min."
    )
    assert parse_label(label, "MDE", "EOH", SEARCH_DATE, SCRAPED_AT).duration_minutes == 45


def test_unknown_currency_is_rejected():
    label = (
        "A partir de 100 euros. Vuelo directo de Avianca. Sale de X el viernes, octubre 16 a las 7:00. "
        "Llega a Y el viernes, octubre 16 a las 8:00. Duración total: 1 h."
    )
    with pytest.raises(ParseError, match="Moneda"):
        parse_label(label, "BOG", "MDE", SEARCH_DATE, SCRAPED_AT)


def test_non_results_page_raises_parse_error():
    with pytest.raises(ParseError):
        parse("<html><head><title>Google Vuelos</title></head><body></body></html>", "BOG", "MDE", SEARCH_DATE)


def test_results_page_without_flights_returns_empty():
    page = "<html><head><title>De Bogotá a Medellín | Google Vuelos</title></head><body></body></html>"
    assert parse(page, "BOG", "MDE", SEARCH_DATE) == []


def test_layout_change_raises_parse_error():
    page = '<html><head><title>X</title></head><body><li aria-label="A partir de un formato nuevo"></li></body></html>'
    with pytest.raises(ParseError, match="Ninguna"):
        parse(page, "BOG", "MDE", SEARCH_DATE)


def test_make_fixture_roundtrip():
    page = load("google_flights_clo_smr_2026-10-16.html")
    again = make_fixture(page)
    assert parse(again, "CLO", "SMR", SEARCH_DATE, SCRAPED_AT) == parse(page, "CLO", "SMR", SEARCH_DATE, SCRAPED_AT)


def test_build_params_requests_one_way_in_cop():
    params = build_params("BOG", "MDE", SEARCH_DATE)
    assert params["q"] == "Flights from BOG to MDE on 2026-10-16 one way"
    assert params["curr"] == "COP" and params["hl"] == "es"
