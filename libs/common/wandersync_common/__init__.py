"""Utilidades compartidas por los microservicios de WanderSync.

Uso típico en un servicio:

    from wandersync_common import Database, ServiceSettings, create_base, create_service_app
"""

from wandersync_common.app_factory import create_service_app
from wandersync_common.config import ServiceSettings
from wandersync_common.db import Database, create_base
from wandersync_common.errors import AppError

__all__ = ["AppError", "Database", "ServiceSettings", "create_base", "create_service_app"]
