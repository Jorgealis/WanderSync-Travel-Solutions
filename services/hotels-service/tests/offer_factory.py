from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import Reservation
from app.models import RoomOffer as Offer

INVENTORY_COLUMN = "rooms_available"


def build_offer(source: str, external_id: str, available: int, price: Decimal) -> Offer:
    check_in = date.today() + timedelta(days=30)
    return Offer(
        source=source, external_id=external_id, hotel_code="TEST", hotel_name="Test Hotel", city_code="MDE",
        room_code="DBL.ST", room_name="Double", room_type="DOUBLE", board_code="RO", board_name="ROOM ONLY",
        max_guests=2, check_in=check_in, check_out=check_in + timedelta(days=3),
        price_per_night=price / 3, price_total=price, price_original=price, currency_original="EUR",
        rooms_total=max(available, 1), rooms_available=available, scraped_at=datetime.now(timezone.utc),
    )
