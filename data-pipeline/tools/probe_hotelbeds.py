"""Prueba única de la API de Hotelbeds (tarea 2.5): como máximo 2 peticiones.

1. Content API: destinos de Colombia → para conocer el código de Medellín.
2. Booking API: disponibilidad y precios de hoteles en ese destino para una fecha.

    docker compose run --rm --no-deps prefect-worker python -m tools.probe_hotelbeds

Lee HOTELBEDS_API_KEY / HOTELBEDS_API_SECRET del entorno y nunca los imprime.
Autenticación de Hotelbeds: cabecera Api-key + X-Signature = SHA-256(key + secret + timestamp Unix).
"""

import hashlib
import json
import os
import sys
import time
from datetime import date, timedelta

import httpx


def signed_headers(key: str, secret: str) -> dict[str, str]:
    signature = hashlib.sha256(f"{key}{secret}{int(time.time())}".encode()).hexdigest()
    return {
        "Api-key": key,
        "X-Signature": signature,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }


def main() -> int:
    key = os.environ.get("HOTELBEDS_API_KEY", "").strip()
    secret = os.environ.get("HOTELBEDS_API_SECRET", "").strip()
    base = os.environ.get("HOTELBEDS_BASE_URL", "https://api.test.hotelbeds.com").rstrip("/")
    if not key or not secret:
        print("Faltan HOTELBEDS_API_KEY y/o HOTELBEDS_API_SECRET en .env")
        return 1
    print(f"Usando {base} con una clave de {len(key)} caracteres (no se muestra)\n")

    with httpx.Client(timeout=30) as client:
        # --- 1. Destinos de Colombia ------------------------------------------
        r = client.get(
            f"{base}/hotel-content-api/1.0/locations/destinations",
            params={"fields": "code,name,countryCode", "countryCodes": "CO",
                    "language": "CAS", "from": 1, "to": 100},
            headers=signed_headers(key, secret),
        )
        print(f"[1] Destinos CO: HTTP {r.status_code}")
        if r.status_code != 200:
            print(r.text[:500])
            return 1
        destinations = r.json().get("destinations", [])
        print("    ", ", ".join(f"{d['code']}={d.get('name', {}).get('content', '?')}" for d in destinations[:40]))
        medellin = next((d["code"] for d in destinations
                         if "medell" in d.get("name", {}).get("content", "").lower()), None)
        if medellin is None:
            print("No se encontró Medellín entre los destinos; revisar la lista anterior.")
            return 1

        # --- 2. Disponibilidad y precios --------------------------------------
        check_in = date.today() + timedelta(days=7)
        body = {
            "stay": {"checkIn": check_in.isoformat(), "checkOut": (check_in + timedelta(days=3)).isoformat()},
            "occupancies": [{"rooms": 1, "adults": 2, "children": 0}],
            "destination": {"code": medellin},
        }
        r = client.post(f"{base}/hotel-api/1.0/hotels", json=body,
                        headers={**signed_headers(key, secret), "Content-Type": "application/json"})
        print(f"\n[2] Disponibilidad {medellin} {body['stay']}: HTTP {r.status_code}")
        if r.status_code != 200:
            print(r.text[:500])
            return 1
        hotels = r.json().get("hotels", {})
        items = hotels.get("hotels", [])
        print(f"    {hotels.get('total', len(items))} hoteles con disponibilidad")
        for h in items[:8]:
            print(f"    - {h.get('name')} | {h.get('categoryName')} | desde {h.get('minRate')} {h.get('currency')} | {len(h.get('rooms', []))} tipos de habitación")
        if items:
            sample = {k: items[0].get(k) for k in ("code", "name", "categoryCode", "categoryName",
                                                   "destinationCode", "zoneName", "latitude", "longitude",
                                                   "minRate", "maxRate", "currency")}
            room = (items[0].get("rooms") or [{}])[0]
            rate = (room.get("rates") or [{}])[0]
            sample["room_example"] = {"code": room.get("code"), "name": room.get("name"),
                                      "net": rate.get("net"), "boardName": rate.get("boardName"),
                                      "adults": rate.get("adults"), "allotment": rate.get("allotment")}
            print("\nEjemplo de registro:\n" + json.dumps(sample, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
