from wandersync_common import create_service_app
from .config import settings
from .db import db
from .router import router

app = create_service_app(settings, db, routers=[router])
