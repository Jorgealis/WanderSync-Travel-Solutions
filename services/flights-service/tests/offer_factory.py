from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import FlightOffer as Offer
from app.models import Reservation

INVENTORY_COLUMN = "seats_available"


def build_offer(source: str, external_id: str, available: int, price: Decimal) -> Offer:
    departure = datetime.now(timezone.utc) + timedelta(days=30)
    return Offer(
        source=source, external_id=external_id, airline="Test Air", origin="BOG", destination="MDE",
        departure_at=departure, arrival_at=departure + timedelta(hours=1), cabin_class="ECONOMY",
        price=price, price_original=price * 4000, currency_original="COP",
        seats_total=max(available, 1), seats_available=available, scraped_at=datetime.now(timezone.utc),
    )
