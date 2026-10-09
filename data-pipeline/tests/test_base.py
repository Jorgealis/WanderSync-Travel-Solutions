"""Pruebas del cliente "educado" (PoliteClient) con un transporte HTTP simulado: sin red."""

import random

import httpx
import pytest

from scrapers.base import (
    PoliteClient,
    RequestBudgetExceeded,
    ScraperSettings,
    SourceBlockedError,
    TransientSourceError,
)

URL = "https://source.example/search"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make_client(handler, clock=None, **settings) -> PoliteClient:
    clock = clock or FakeClock()
    return PoliteClient(
        ScraperSettings(**settings),
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock,
        rng=random.Random(0),
    )


def ok(_request):
    return httpx.Response(200, text="<html></html>")


def test_waits_min_delay_between_requests():
    clock = FakeClock()
    client = make_client(ok, clock, min_delay_seconds=5)
    client.get(URL)
    clock.now += 1.5  # pasa algo de tiempo entre una petición y la siguiente
    client.get(URL)
    assert clock.slept == [pytest.approx(3.5)]


def test_request_budget_is_enforced():
    client = make_client(ok, min_delay_seconds=0, max_requests_per_run=2)
    client.get(URL)
    client.get(URL)
    with pytest.raises(RequestBudgetExceeded):
        client.get(URL)


def test_sends_configured_headers():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200)

    make_client(handler, user_agent="UA-de-prueba", accept_language="es-CO").get(URL)
    assert seen["user-agent"] == "UA-de-prueba"
    assert seen["accept-language"] == "es-CO"


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_errors_are_transient(status):
    with pytest.raises(TransientSourceError):
        make_client(lambda r: httpx.Response(status)).get(URL)


def test_network_errors_are_transient():
    def handler(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(TransientSourceError):
        make_client(handler).get(URL)


def test_rate_limit_is_blocking_not_transient():
    with pytest.raises(SourceBlockedError, match="429"):
        make_client(lambda r: httpx.Response(429)).get(URL)


@pytest.mark.parametrize(
    "redirect_to",
    [
        "https://www.google.com/sorry/index?continue=x",
        "https://consent.google.com/ml?continue=x",
        "https://www.google.com/travel/flights/unsupported?q=x",
    ],
)
def test_captcha_consent_and_unsupported_redirects_are_blocking(redirect_to):
    def handler(request):
        if request.url == httpx.URL(URL):
            return httpx.Response(302, headers={"Location": redirect_to})
        return httpx.Response(200, text="<html></html>")

    with pytest.raises(SourceBlockedError):
        make_client(handler).get(URL)


def test_simulated_fault_does_not_hit_the_source():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    with pytest.raises(TransientSourceError, match="SIMULADO"):
        make_client(handler, fault_rate=1.0).get(URL)
    assert calls == []


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("SCRAPER_MIN_DELAY_SECONDS", "7.5")
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_RUN", "3")
    monkeypatch.setenv("SCRAPER_FAULT_RATE", "0.25")
    monkeypatch.delenv("SCRAPER_USER_AGENT", raising=False)
    settings = ScraperSettings.from_env()
    assert settings.min_delay_seconds == 7.5
    assert settings.max_requests_per_run == 3
    assert settings.fault_rate == 0.25
    assert settings.user_agent.startswith("Mozilla/5.0")
