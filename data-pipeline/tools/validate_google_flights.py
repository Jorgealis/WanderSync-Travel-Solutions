"""Validación del scraper de Google Flights en todas las rutas y fechas configuradas (tarea 2.4).

Hace (rutas × fechas) peticiones REALES con la política de scraping responsable
(pausa entre peticiones, límite por ejecución) y reporta por cada búsqueda: vuelos,
etiquetas descartadas y anomalías. Si la fuente bloquea, se detiene de inmediato.

    python -m tools.validate_google_flights                    # usa INGEST_ROUTES e INGEST_DATE_OFFSETS
    python -m tools.validate_google_flights --json /tmp/r.json # además guarda el detalle

Volver a ejecutarlo si las pruebas del parser empiezan a fallar o antes de la demo.
"""

import argparse
import json
import os
import time
from collections import Counter
from datetime import date, timedelta

from scrapers.base import PoliteClient, ScraperError, ScraperSettings, SourceBlockedError
from scrapers.google_flights import fetch, parse_with_report


def search_plan() -> list[tuple[str, str, date]]:
    routes = [r.strip() for r in os.environ.get("INGEST_ROUTES", "BOG-MDE").split(",") if r.strip()]
    offsets = [int(o) for o in os.environ.get("INGEST_DATE_OFFSETS", "7,14,30").split(",")]
    today = date.today()
    return [
        (route.split("-")[0], route.split("-")[1], today + timedelta(days=offset))
        for offset in offsets
        for route in routes
    ]


def check(origin: str, destination: str, day: date, client: PoliteClient) -> dict:
    started = time.monotonic()
    page = fetch(client, origin, destination, day)
    records, failures = parse_with_report(page, origin, destination, day)
    prices = [r.price_original for r in records]
    anomalies = []
    for r in records:
        computed = int((r.arrival_at - r.departure_at).total_seconds() // 60)
        if computed != r.duration_minutes:
            anomalies.append(f"duración publicada {r.duration_minutes} != calculada {computed} ({r.airline} {r.departure_at:%H:%M})")
    return {
        "route": f"{origin}-{destination}",
        "date": day.isoformat(),
        "status": "ok",
        "flights": len(records),
        "discarded_labels": len(failures),
        "discard_reasons": failures[:5],
        "min_price": str(min(prices)) if prices else None,
        "max_price": str(max(prices)) if prices else None,
        "currencies": sorted({r.currency_original for r in records}),
        "airlines": dict(Counter(r.airline for r in records)),
        "stops": dict(Counter(r.stops for r in records)),
        "with_operator": sum(r.operated_by is not None for r in records),
        "next_day_arrivals": sum(r.arrival_at.date() > r.departure_at.date() for r in records),
        "anomalies": anomalies,
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", metavar="PATH", help="guardar el detalle completo en JSON")
    args = parser.parse_args()

    plan = search_plan()
    settings = ScraperSettings.from_env()
    print(f"{len(plan)} búsquedas, pausa mínima {settings.min_delay_seconds}s, límite {settings.max_requests_per_run}\n")
    print(f"{'ruta':8} {'fecha':10} {'vuelos':>6} {'desc.':>5} {'precio mín':>11} {'escalas':14} anomalías")

    results = []
    with PoliteClient(settings) as client:
        for origin, destination, day in plan:
            try:
                result = check(origin, destination, day, client)
            except SourceBlockedError as exc:
                results.append({"route": f"{origin}-{destination}", "date": day.isoformat(), "status": "BLOCKED", "error": str(exc)})
                print(f"{origin}-{destination} {day} BLOQUEADO: {exc}\nSe detiene la validación (no se insiste contra una fuente que bloquea).")
                break
            except ScraperError as exc:
                result = {"route": f"{origin}-{destination}", "date": day.isoformat(), "status": type(exc).__name__, "error": str(exc)}
            results.append(result)
            if result["status"] == "ok":
                stops = ",".join(f"{k}:{v}" for k, v in sorted(result["stops"].items()))
                print(f"{result['route']:8} {result['date']:10} {result['flights']:>6} {result['discarded_labels']:>5} "
                      f"{result['min_price'] or '-':>11} {stops:14} {len(result['anomalies'])}")
            else:
                print(f"{result['route']:8} {result['date']:10} {result['status']}: {result['error'][:80]}")

    ok = [r for r in results if r["status"] == "ok"]
    print(f"\nResumen: {len(ok)}/{len(plan)} búsquedas correctas, "
          f"{sum(r['flights'] for r in ok)} vuelos, {sum(r['discarded_labels'] for r in ok)} etiquetas descartadas, "
          f"{sum(len(r['anomalies']) for r in ok)} anomalías, {client.requests_made} peticiones.")
    airlines = Counter()
    for r in ok:
        airlines.update(r["airlines"])
    print("Aerolíneas:", dict(airlines.most_common()))
    reasons = [reason for r in ok for reason in r["discard_reasons"]] + [a for r in ok for a in r["anomalies"]]
    for reason in list(dict.fromkeys(reasons))[:10]:
        print("  -", reason[:160])

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        print(f"Detalle guardado en {args.json}")


if __name__ == "__main__":
    main()
