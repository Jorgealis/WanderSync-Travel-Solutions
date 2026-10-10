"""Tipos de cambio para normalizar el catálogo a USD.

Fuentes públicas (también son "ingesta de fuentes reales"):
- COP por USD: TRM oficial de Colombia, Superintendencia Financiera, publicada en
  datos.gov.co (dataset 32sa-8pi3, API Socrata pública).
- USD por EUR: tipos de referencia del Banco Central Europeo vía Frankfurter.

Si alguna no responde, se usan FX_COP_PER_USD / FX_USD_PER_EUR del entorno y el
resultado lo indica (`source="fallback"`), para que el artefacto de Prefect lo muestre.
"""

import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import httpx

TRM_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"
ECB_URL = "https://api.frankfurter.dev/v1/latest"
CENT = Decimal("0.01")


class UnsupportedCurrency(ValueError):
    pass


@dataclass(frozen=True)
class FxRates:
    cop_per_usd: Decimal
    usd_per_eur: Decimal
    source: str  # "trm+ecb" | "fallback" | combinaciones
    as_of: str

    def to_usd(self, amount: Decimal, currency: str) -> Decimal:
        if currency == "USD":
            value = amount
        elif currency == "COP":
            value = amount / self.cop_per_usd
        elif currency == "EUR":
            value = amount * self.usd_per_eur
        else:
            raise UnsupportedCurrency(f"Moneda no soportada: {currency}")
        return value.quantize(CENT, rounding=ROUND_HALF_UP)


def fallback_rates() -> FxRates:
    return FxRates(
        cop_per_usd=Decimal(os.environ.get("FX_COP_PER_USD", "3200")),
        usd_per_eur=Decimal(os.environ.get("FX_USD_PER_EUR", "1.12")),
        source="fallback",
        as_of="config",
    )


def fetch_rates(client: httpx.Client | None = None) -> FxRates:
    """Consulta ambas fuentes; cada una cae por separado al valor de respaldo."""
    fallback = fallback_rates()
    own_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=True)
    sources, dates = [], []
    try:
        try:
            response = client.get(TRM_URL, params={"$order": "vigenciadesde DESC", "$limit": "1"})
            response.raise_for_status()
            latest = response.json()[0]
            cop_per_usd = Decimal(latest["valor"])
            sources.append("trm")
            dates.append(latest["vigenciadesde"][:10])
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            cop_per_usd = fallback.cop_per_usd
            sources.append("fallback-cop")

        try:
            response = client.get(ECB_URL, params={"base": "EUR", "symbols": "USD"})
            response.raise_for_status()
            payload = response.json()
            usd_per_eur = Decimal(str(payload["rates"]["USD"]))
            sources.append("ecb")
            dates.append(payload["date"])
        except (httpx.HTTPError, KeyError, ValueError):
            usd_per_eur = fallback.usd_per_eur
            sources.append("fallback-eur")
    finally:
        if own_client:
            client.close()

    return FxRates(cop_per_usd, usd_per_eur, "+".join(sources), max(dates) if dates else "config")
