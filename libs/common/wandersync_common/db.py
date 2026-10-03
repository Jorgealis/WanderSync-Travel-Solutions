from collections.abc import AsyncIterator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from wandersync_common.config import ServiceSettings

# Nombres de constraints deterministas: Alembic genera migraciones estables.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def create_base(schema: str) -> type[DeclarativeBase]:
    """Base declarativa cuyas tablas viven en el esquema del servicio."""

    class Base(DeclarativeBase):
        metadata = MetaData(schema=schema, naming_convention=NAMING_CONVENTION)

    return Base


def engine_connect_args(settings: ServiceSettings) -> dict:
    # search_path limitado al esquema propio: el servicio no "ve" otros esquemas
    # ni siquiera por accidente (además de no tener privilegios sobre ellos).
    return {
        "server_settings": {
            "search_path": settings.db_schema,
            "application_name": settings.service_name,
        }
    }


class Database:
    def __init__(self, settings: ServiceSettings) -> None:
        self.engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            connect_args=engine_connect_args(settings),
        )
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def session(self) -> AsyncIterator[AsyncSession]:
        """Dependencia FastAPI: `session: Annotated[AsyncSession, Depends(db.session)]`."""
        async with self.sessionmaker() as session:
            yield session

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
