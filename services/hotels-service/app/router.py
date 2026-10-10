from wandersync_common.reservations import create_reservation_router

from .config import settings
from .db import db
from .models import RoomOfferModel, RoomReservationModel


router = create_reservation_router(
    tag="Hotel Reservations",
    offer_model=RoomOfferModel,
    reservation_model=RoomReservationModel,
    inventory_field="rooms_available",
    unit_price_field="price_total",
    session_dependency=db.session,
    fault_injection_enabled=settings.enable_fault_injection,
)
