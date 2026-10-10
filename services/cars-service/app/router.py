from wandersync_common.reservations import create_reservation_router

from .config import settings
from .db import db
from .models import CarOfferModel, CarReservationModel


router = create_reservation_router(
    tag="Car Reservations",
    offer_model=CarOfferModel,
    reservation_model=CarReservationModel,
    inventory_field="units_available",
    unit_price_field="price_total",
    session_dependency=db.session,
    fault_injection_enabled=settings.enable_fault_injection,
    quantity_must_be_one=True,
)
