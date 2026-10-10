from wandersync_common.reservations import create_reservation_router

from .config import settings
from .db import db
from .models import FlightOfferModel, FlightReservationModel


router = create_reservation_router(
    tag="Flight Reservations",
    offer_model=FlightOfferModel,
    reservation_model=FlightReservationModel,
    inventory_field="seats_available",
    unit_price_field="price",
    session_dependency=db.session,
    fault_injection_enabled=settings.enable_fault_injection,
)
