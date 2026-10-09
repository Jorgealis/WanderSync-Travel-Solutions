"""Lógica compartida de alembic/env.py para todos los servicios.

Cada servicio guarda su tabla `alembic_version` en SU esquema, así las migraciones
de un servicio nunca interfieren con las de otro aunque compartan la instancia de BD.
"""

import asyncio

from alembic import context
from sqlalchemy import MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from wandersync_common.config import ServiceSettings
from wandersync_common.db import engine_connect_args


def _include_object(_object, name, type_, _reflected, _compare_to) -> bool:
    # La tabla de versiones de Alembic vive en el esquema del servicio pero no está en
    # los modelos: sin esto, autogenerate propone borrarla.
    return not (type_ == "table" and name == "alembic_version")


def run_migrations(target_metadata: MetaData, settings: ServiceSettings) -> None:
    configure_kwargs = {
        "target_metadata": target_metadata,
        "version_table_schema": settings.db_schema,
        "include_schemas": False,
        "include_object": _include_object,
        "compare_type": True,
    }

    if context.is_offline_mode():
        context.configure(
            url=settings.database_url.render_as_string(hide_password=False),
            literal_binds=True,
            **configure_kwargs,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    def do_run_migrations(connection: Connection) -> None:
        context.configure(connection=connection, **configure_kwargs)
        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
            connect_args=engine_connect_args(settings),
        )
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await engine.dispose()

    asyncio.run(run_async_migrations())
