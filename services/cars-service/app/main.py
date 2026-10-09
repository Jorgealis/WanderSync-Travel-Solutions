from wandersync_common import create_service_app
from wandersync_common.reservations import InventorySpec, reservation_router

from app.config import settings
from app.db import db
from app.models import CarOffer, Reservation

inventory = InventorySpec(
    offer_model=CarOffer,
    reservation_model=Reservation,
    available_column="units_available",
    unit_price=lambda offer: offer.price_total,
)

app = create_service_app(settings, db, routers=[reservation_router(db, inventory, settings)])
