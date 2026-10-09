from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import CarOffer as Offer
from app.models import Reservation

INVENTORY_COLUMN = "units_available"


def build_offer(source: str, external_id: str, available: int, price: Decimal) -> Offer:
    pickup = date.today() + timedelta(days=30)
    return Offer(
        source=source, external_id=external_id, company="Test Rent", model="Test Car", category="ECONOMY",
        transmission="MANUAL", seats=5, city_code="MDE", pickup_date=pickup, dropoff_date=pickup + timedelta(days=3),
        price_per_day=price / 3, price_total=price, price_original=price * 4000, currency_original="COP",
        units_total=max(available, 1), units_available=available, scraped_at=datetime.now(timezone.utc),
    )
