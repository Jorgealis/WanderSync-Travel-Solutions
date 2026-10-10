"""Pruebas del scraper de RutaFácil (fuente SIMULADA de autos), sin red.

Fixtures generados desde el propio servicio mock con el caos desactivado
(MDE, 16→19 oct 2026, 2 páginas con un vehículo repetido entre ellas).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from scrapers.base import ParseError, PoliteClient, ScraperSettings, TransientSourceError
from scrapers.mock_car_rental import SOURCE, _parse_dates, _parse_price, fetch_all, parse_page

FIXTURES = Path(__file__).parent / "fixtures"
PICKUP, DROPOFF = date(2026, 10, 16), date(2026, 10, 19)
SCRAPED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def page(n: int) -> str:
    return (FIXTURES / f"mock_cars_mde_2026-10-16_p{n}.html").read_text(encoding="utf-8")


def test_parses_first_page():
    records, failures, has_next = parse_page(page(1), "MDE", PICKUP, DROPOFF, SCRAPED_AT)
    assert (len(records), failures, has_next) == (8, [], True)
    for r in records:
        assert r.source == SOURCE and r.city_code == "MDE" and r.days == 3
        assert r.currency_original == "COP"
        assert r.price_per_day_original > 0
        assert abs(r.price_original - r.price_per_day_original * 3) < 1  # total coherente con el diario
        assert r.category in {"ECONOMY", "COMPACT", "SUV", "VAN", "LUXURY"}
        assert r.external_id.startswith("VEH-")
        assert not r.model.endswith("similar")


def test_last_page_has_no_next():
    _records, _failures, has_next = parse_page(page(2), "MDE", PICKUP, DROPOFF, SCRAPED_AT)
    assert has_next is False


def test_missing_transmission_is_kept_as_none():
    records = parse_page(page(1), "MDE", PICKUP, DROPOFF, SCRAPED_AT)[0] + parse_page(page(2), "MDE", PICKUP, DROPOFF, SCRAPED_AT)[0]
    assert any(r.transmission is None for r in records)  # se completa en la normalización (2.9)
    assert {r.transmission for r in records} - {None} <= {"MANUAL", "AUTOMATIC"}


@pytest.mark.parametrize(
    ("text", "per_day", "total"),
    [
        ("COP 113.700 / día", "113700", "341100"),
        ("114600 pesos por día", "114600", "343800"),
        ("$ 143,400 diarios", "143400", "430200"),
        ("Total 3 días: COP 360.000", "120000.00", "360000"),
    ],
)
def test_all_price_formats(text, per_day, total):
    assert _parse_price(text, 3) == (Decimal(per_day), Decimal(total))


def test_total_for_other_duration_is_rejected():
    with pytest.raises(ParseError):
        _parse_price("Total 5 días: COP 600.000", 3)


@pytest.mark.parametrize("text", ["16/10/2026 → 19/10/2026", "del 2026-10-16 al 2026-10-19"])
def test_both_date_formats(text):
    assert _parse_dates(text) == (PICKUP, DROPOFF)


def test_unknown_layout_raises():
    with pytest.raises(ParseError):
        parse_page("<html><body><p>Nuevo diseño</p></body></html>", "MDE", PICKUP, DROPOFF)


def _serving_fixtures(fail_first: int = 0):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= fail_first:
            return httpx.Response(503, text="Error 503")
        return httpx.Response(200, text=page(int(request.url.params["pagina"])))

    return handler, calls


def _client(handler) -> PoliteClient:
    return PoliteClient(ScraperSettings(min_delay_seconds=0), transport=httpx.MockTransport(handler))


def test_fetch_all_follows_pagination_and_drops_duplicate():
    handler, calls = _serving_fixtures()
    with _client(handler) as client:
        records, failures, pages = fetch_all(client, "http://mock", "MDE", PICKUP, DROPOFF)
    assert (pages, calls["n"], failures) == (2, 2, [])
    assert len(records) == 15  # 8 + 8 con uno repetido
    assert len({r.external_id for r in records}) == 15


def test_server_error_is_transient():
    handler, _ = _serving_fixtures(fail_first=1)
    with _client(handler) as client, pytest.raises(TransientSourceError):
        fetch_all(client, "http://mock", "MDE", PICKUP, DROPOFF)
