from logging.config import fileConfig

from alembic import context
from wandersync_common.alembic_env import run_migrations

from app.config import settings
from app.models import Base

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

run_migrations(Base.metadata, settings)
