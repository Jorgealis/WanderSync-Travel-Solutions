from wandersync_common import create_service_app

from app.config import settings
from app.db import db

# Los routers del dominio (reservations, etc.) se agregan en la Fase 2.
app = create_service_app(settings, db, routers=[])
