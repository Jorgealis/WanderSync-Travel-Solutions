from wandersync_common import create_service_app

from app.config import settings
from app.db import db

# Los routers del dominio (órdenes, SAGA) se agregan en la Fase 3.
app = create_service_app(settings, db, routers=[])
