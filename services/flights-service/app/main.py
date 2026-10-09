from wandersync_common import create_service_app
from wandersync_common.reservations import InventorySpec, reservation_router

from app.config import settings
from app.db import db
from app.models import FlightOffer, Reservation

inventory = InventorySpec(
    offer_model=FlightOffer,
    reservation_model=Reservation,
    available_column="seats_available",
    unit_price=lambda offer: offer.price,
)

app = create_service_app(settings, db, routers=[reservation_router(db, inventory, settings)])
