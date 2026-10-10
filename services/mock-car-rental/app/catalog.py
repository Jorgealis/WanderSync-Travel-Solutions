"""Generador determinista del catálogo simulado de alquiler de autos.

Los MODELOS y CATEGORÍAS son reales del mercado colombiano; las EMPRESAS son ficticias,
para no atribuir precios inventados a marcas reales. Todo el sitio se declara simulado.

Determinismo: las mismas (ciudad, fechas) producen siempre las mismas ofertas (IDs
estables, como en una fuente real), y el precio varía un poco cada día para que la
ingesta tenga actualizaciones que registrar.
"""

import hashlib
import random
from dataclasses import dataclass
from datetime import date

CITIES = {
    "MDE": "Medellín",
    "CTG": "Cartagena",
    "SMR": "Santa Marta",
    "BOG": "Bogotá",
    "ADZ": "San Andrés",
    "CLO": "Cali",
}

# (código, nombre, formato de precio, formato de fecha). Cada empresa publica distinto,
# como ocurre al agregar varias fuentes reales.
COMPANIES = [
    ("AND", "Andes Rent a Car", "cop_per_day", "slash"),
    ("CRB", "Caribe Wheels", "dollar_sign_per_day", "iso"),
    ("RVA", "Ruta Verde Autos", "total_cop", "slash"),
    ("MTN", "Montaña Car Rental", "pesos_words_per_day", "iso"),
    ("PCF", "Pacífico Drive", "cop_per_day", "iso"),
]

# categoría publicada (en español) → (modelos reales, puestos, transmisión típica, rango COP/día)
CATEGORIES = {
    "Económico": (["Kia Picanto", "Chevrolet Spark GT", "Renault Kwid"], 5, "Manual", (110_000, 150_000)),
    "Compacto": (["Chevrolet Onix", "Renault Logan", "Mazda 2", "Suzuki Swift"], 5, "Manual", (140_000, 195_000)),
    "SUV / Camioneta": (["Renault Duster", "Kia Sportage", "Nissan Kicks", "Mazda CX-30", "Toyota Fortuner"], 5, "Automática", (220_000, 380_000)),
    "Van": (["Hyundai H1", "Toyota Hiace"], 12, "Manual", (350_000, 460_000)),
    "Lujo": (["Mercedes-Benz Clase C", "BMW Serie 3", "Audi A4"], 5, "Automática", (520_000, 800_000)),
}


@dataclass(frozen=True)
class Vehicle:
    vehicle_id: str
    company: str
    price_format: str
    date_format: str
    model: str
    category: str
    seats: int | None
    transmission: str | None
    price_per_day_cop: int


def _rng(*parts: object) -> random.Random:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def vehicles_for(city: str, pickup: date, dropoff: date, seed: int, today: date) -> list[Vehicle]:
    rng = _rng(seed, city, pickup, dropoff)
    daily_drift = 1 + (_rng(seed, city, pickup, dropoff, today).random() - 0.5) * 0.08  # ±4 % diario
    vehicles = []
    for company_code, company, price_format, date_format in COMPANIES:
        for category, (models, seats, transmission, (low, high)) in CATEGORIES.items():
            if rng.random() < 0.35:  # no todas las empresas tienen todas las categorías
                continue
            model = rng.choice(models)
            base = rng.randint(low, high)
            vehicle_id = "VEH-" + company_code + "-" + hashlib.sha1(f"{city}{pickup}{dropoff}{company_code}{model}".encode()).hexdigest()[:10]
            vehicles.append(Vehicle(
                vehicle_id=vehicle_id,
                company=company,
                price_format=price_format,
                date_format=date_format,
                model=model,
                category=category,
                # Campos faltantes, como en una fuente real:
                seats=None if rng.random() < 0.12 else seats,
                transmission=None if rng.random() < 0.10 else transmission,
                price_per_day_cop=int(round(base * daily_drift, -2)),
            ))
    vehicles.sort(key=lambda v: v.price_per_day_cop)
    return vehicles


def format_price(vehicle: Vehicle, days: int) -> str:
    per_day = vehicle.price_per_day_cop
    thousands = f"{per_day:,}".replace(",", ".")
    if vehicle.price_format == "cop_per_day":
        return f"COP {thousands} / día"
    if vehicle.price_format == "dollar_sign_per_day":
        return f"$ {per_day:,} diarios"  # separador de miles con coma
    if vehicle.price_format == "total_cop":
        total = f"{per_day * days:,}".replace(",", ".")
        return f"Total {days} días: COP {total}"
    return f"{per_day} pesos por día"


def format_dates(vehicle: Vehicle, pickup: date, dropoff: date) -> str:
    if vehicle.date_format == "slash":
        return f"{pickup:%d/%m/%Y} → {dropoff:%d/%m/%Y}"
    return f"del {pickup.isoformat()} al {dropoff.isoformat()}"
