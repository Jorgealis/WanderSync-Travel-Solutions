from wandersync_common import create_service_app

from app.config import settings
from app.db import db

# Los routers del dominio (usuarios, sesiones) se agregan en la Fase 4.
app = create_service_app(settings, db, routers=[])
