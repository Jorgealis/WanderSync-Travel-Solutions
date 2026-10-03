from wandersync_common import Database, create_base

from app.config import settings

db = Database(settings)
Base = create_base(settings.db_schema)
