"""Pruebas del cliente de Hotelbeds sin red y sin gastar cuota.

El fixture es una respuesta real (CTG, 16→19 oct 2026, 1 habitación, 2 adultos) reducida
a los campos que usa el parser:
    python -m scrapers.hotelbeds CTG 2026-10-16 3 --save-fixture tests/fixtures/...
"""

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from scrapers.base import ParseError, ScraperSettings, SourceBlockedError
from scrapers.hotelbeds import (
    SOURCE,
    HotelbedsSettings,
    build_request,
    fetch,
    make_client,
    parse,
    parse_stars,
    parse_with_report,
    signature,
)
from scrapers.quota import DailyQuota, DailyQuotaExceeded

FIXTURE = Path(__file__).parent / "fixtures" / "hotelbeds_ctg_2026-10-16_3n.json"
SCRAPED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
SETTINGS = HotelbedsSettings(api_key="k" * 32, api_secret="s" * 10, base_url="https://api.test.example")


@pytest.fixture(scope="module")
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ctg(payload):
    return parse_with_report(payload, SCRAPED_AT)


def test_parses_every_rate_of_real_response(ctg):
    records, failures = ctg
    assert failures == []
    assert len({r.hotel_code for r in records}) == 68
    assert len(records) == 326  # una oferta por hotel + habitación + régimen


def test_records_are_consistent(ctg):
    records, _ = ctg
    assert len({r.external_id for r in records}) == len(records)
    for r in records:
        assert r.source == SOURCE
        assert r.city_code == "CTG"
        assert (r.check_in, r.check_out, r.nights) == (date(2026, 10, 16), date(2026, 10, 19), 3)
        assert r.currency_original == "EUR"
        assert r.price_original > 0
        assert r.allotment is not None and r.allotment >= 0
        assert r.max_guests == 2
        assert r.external_id == f"{r.hotel_code}:{r.room_code}:{r.board_code}:2026-10-16:2026-10-19"
        assert r.room_type in {"SINGLE", "DOUBLE", "TWIN", "SUITE", "FAMILY", "OTHER"}


def test_exact_values_of_a_real_offer(ctg):
    records, _ = ctg
    offer = next(
        r for r in records
        if r.hotel_name == "Hotel Playa Norte" and r.room_name == "Double standard" and r.board_name == "ROOM ONLY"
    )
    assert offer.price_original == Decimal("92.76")
    assert offer.allotment == 13
    assert offer.stars == 3
    assert offer.room_type == "DOUBLE"
    assert offer.latitude is not None and offer.longitude is not None


def test_keeps_cheapest_rate_per_room_and_board():
    payload = {"hotels": {"checkIn": "2026-10-16", "checkOut": "2026-10-18", "hotels": [{
        "code": 1, "name": "H", "categoryCode": "4EST", "categoryName": "4 STARS", "destinationCode": "MDE",
        "currency": "EUR",
        "rooms": [{"code": "DBL.ST", "name": "Double", "rates": [
            {"net": "200.00", "boardCode": "RO", "boardName": "ROOM ONLY", "adults": 2, "allotment": 3},
            {"net": "150.00", "boardCode": "RO", "boardName": "ROOM ONLY", "adults": 2, "allotment": 5},
            {"net": "180.00", "boardCode": "BB", "boardName": "BED AND BREAKFAST", "adults": 2, "allotment": 1},
        ]}],
    }]}}
    records = {r.board_code: r for r in parse(payload, SCRAPED_AT)}
    assert records["RO"].price_original == Decimal("150.00") and records["RO"].allotment == 5
    assert records["BB"].price_original == Decimal("180.00")
    assert records["RO"].nights == 2


def test_invalid_rate_is_reported_not_fatal():
    payload = {"hotels": {"checkIn": "2026-10-16", "checkOut": "2026-10-17", "hotels": [{
        "code": 1, "name": "H", "destinationCode": "MDE", "currency": "EUR",
        "rooms": [{"code": "DBL.ST", "name": "Double", "rates": [
            {"net": "0", "boardCode": "RO", "boardName": "ROOM ONLY", "adults": 2},
            {"net": "90.00", "boardCode": "BB", "boardName": "BED AND BREAKFAST", "adults": 2},
        ]}],
    }]}}
    records, failures = parse_with_report(payload, SCRAPED_AT)
    assert [r.board_code for r in records] == ["BB"]
    assert len(failures) == 1 and "tarifa neta inválida" in failures[0]


def test_no_availability_returns_empty():
    assert parse({"hotels": {"checkIn": "2026-10-16", "checkOut": "2026-10-19", "total": 0}}) == []


def test_unexpected_payload_raises_parse_error():
    with pytest.raises(ParseError):
        parse({"error": {"code": "X"}})


@pytest.mark.parametrize(
    ("code", "name", "expected"),
    [
        ("5EST", "5 STARS", 5),
        ("H4_5", "4 STARS AND A HALF", 4),
        ("5LUX", "5 STARS LUXURY", 5),
        ("APTH3", "APARTHOTEL 3*", 3),
        ("BOU", "BOUTIQUE", None),
        ("SPC", "WITHOUT OFFICIAL CATEGORY", None),
        (None, None, None),
    ],
)
def test_stars_from_real_categories(code, name, expected):
    assert parse_stars(code, name) == expected


def test_signature_is_sha256_of_key_secret_timestamp():
    expected = hashlib.sha256(b"KEYSECRET1700000000").hexdigest()
    assert signature("KEY", "SECRET", 1700000000) == expected


def test_build_request():
    body = build_request("MDE", date(2026, 10, 16), 5)
    assert body["stay"] == {"checkIn": "2026-10-16", "checkOut": "2026-10-21"}
    assert body["destination"] == {"code": "MDE"}
    assert body["occupancies"] == [{"rooms": 1, "adults": 2, "children": 0}]


def _client(handler):
    return make_client(SETTINGS, ScraperSettings(min_delay_seconds=0), transport=httpx.MockTransport(handler))


def test_fetch_sends_signed_post_and_reserves_quota(tmp_path, payload):
    seen = {}

    def handler(request):
        seen["method"], seen["url"] = request.method, str(request.url)
        seen["headers"], seen["body"] = request.headers, json.loads(request.content)
        return httpx.Response(200, json=payload)

    quota = DailyQuota(tmp_path, SOURCE, daily_budget=5)
    with _client(handler) as client:
        result = fetch(client, SETTINGS, quota, "CTG", date(2026, 10, 16), 3)
    assert seen["method"] == "POST" and seen["url"] == "https://api.test.example/hotel-api/1.0/hotels"
    assert seen["headers"]["api-key"] == SETTINGS.api_key and len(seen["headers"]["x-signature"]) == 64
    assert seen["body"]["destination"] == {"code": "CTG"}
    assert result["hotels"]["total"] == 68
    assert quota.used() == 1


def test_rejected_credentials_are_blocking_and_still_count(tmp_path):
    quota = DailyQuota(tmp_path, SOURCE, daily_budget=5)
    with _client(lambda r: httpx.Response(401, json={"error": "Request signature verification failed"})) as client:
        with pytest.raises(SourceBlockedError, match="credenciales"):
            fetch(client, SETTINGS, quota, "CTG", date(2026, 10, 16), 3)
    assert quota.used() == 1  # la API también cuenta las peticiones fallidas


def test_exhausted_quota_never_calls_the_api(tmp_path):
    calls = []
    quota = DailyQuota(tmp_path, SOURCE, daily_budget=0)
    with _client(lambda r: calls.append(r) or httpx.Response(200, json={})) as client:
        with pytest.raises(DailyQuotaExceeded):
            fetch(client, SETTINGS, quota, "CTG", date(2026, 10, 16), 3)
    assert calls == []


def test_settings_require_credentials(monkeypatch):
    monkeypatch.delenv("HOTELBEDS_API_KEY", raising=False)
    monkeypatch.delenv("HOTELBEDS_API_SECRET", raising=False)
    with pytest.raises(ValueError, match="HOTELBEDS_API_KEY"):
        HotelbedsSettings.from_env()
