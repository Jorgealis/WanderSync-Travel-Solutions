"""Pruebas del contador de cuota diaria compartido (DailyQuota)."""

from datetime import date

import pytest

from scrapers.quota import DailyQuota, DailyQuotaExceeded


def test_reserves_until_budget(tmp_path):
    quota = DailyQuota(tmp_path, "src", daily_budget=3)
    assert [quota.reserve() for _ in range(3)] == [1, 2, 3]
    assert quota.remaining() == 0
    with pytest.raises(DailyQuotaExceeded, match="3/3"):
        quota.reserve()
    assert quota.used() == 3  # un intento rechazado no suma


def test_shared_between_instances(tmp_path):
    # Simula dos workers de Dask distintos usando el mismo volumen.
    a = DailyQuota(tmp_path, "src", daily_budget=2)
    b = DailyQuota(tmp_path, "src", daily_budget=2)
    a.reserve()
    b.reserve()
    with pytest.raises(DailyQuotaExceeded):
        a.reserve()


def test_resets_on_a_new_utc_day(tmp_path):
    day = {"value": date(2026, 10, 9)}
    quota = DailyQuota(tmp_path, "src", daily_budget=1, today=lambda: day["value"])
    quota.reserve()
    with pytest.raises(DailyQuotaExceeded):
        quota.reserve()
    day["value"] = date(2026, 10, 10)
    assert quota.reserve() == 1


def test_sources_are_independent(tmp_path):
    DailyQuota(tmp_path, "hotelbeds", daily_budget=1).reserve()
    assert DailyQuota(tmp_path, "otra", daily_budget=1).reserve() == 1
