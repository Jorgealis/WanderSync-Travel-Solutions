"""Persistencia por lotes del catálogo (tarea 2.10).

Upsert `INSERT ... ON CONFLICT (source, external_id) DO UPDATE` en lotes de
INGEST_BATCH_SIZE, con el usuario `ingest`.

Regla de oro (docs/contratos/modelo-datos.md): el inventario (seats/rooms/units
total y available) se escribe SOLO al insertar una oferta nueva. En una oferta ya
conocida se actualizan precio y metadata. Postgres lo refuerza: `ingest` no tiene
permiso de UPDATE sobre esas columnas.
"""

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import URL, MetaData, Table, create_engine, func, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class CatalogTable:
    schema: str
    table: str
    update_columns: tuple[str, ...]  # deben coincidir con los GRANT UPDATE de la migración


CATALOGS = {
    "flights": CatalogTable("flights", "flight_offers", (
        "price", "currency", "price_original", "currency_original", "operated_by", "flight_number", "stops", "scraped_at",
    )),
    "hotels": CatalogTable("hotels", "room_offers", (
        "hotel_name", "zone_name", "address", "latitude", "longitude", "stars", "category_name", "rating", "room_name",
        "room_type", "board_name", "max_guests", "price_per_night", "price_total", "currency", "price_original",
        "currency_original", "scraped_at",
    )),
    "cars": CatalogTable("cars", "car_offers", (
        "company", "model", "category", "transmission", "seats", "price_per_day", "price_total", "currency",
        "price_original", "currency_original", "scraped_at",
    )),
}


@dataclass(frozen=True)
class UpsertResult:
    inserted: int
    updated: int


def ingest_engine() -> Engine:
    env = os.environ
    url = URL.create(
        "postgresql+psycopg",
        username=env["INGEST_DB_USER"],
        password=env["INGEST_DB_PASSWORD"],
        host=env.get("POSTGRES_HOST", "postgres"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        database=env.get("POSTGRES_DB", "wandersync"),
    )
    return create_engine(url, pool_pre_ping=True, connect_args={"application_name": "wandersync-ingest"})


def _chunks(rows: Sequence[dict], size: int) -> Iterable[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def upsert(engine: Engine, catalog: str, rows: Sequence[dict], batch_size: int = 500) -> UpsertResult:
    if not rows:
        return UpsertResult(0, 0)
    spec = CATALOGS[catalog]
    table = Table(spec.table, MetaData(schema=spec.schema), autoload_with=engine)
    inserted = updated = 0
    with engine.begin() as connection:
        for batch in _chunks(rows, batch_size):
            stmt = insert(table).values(list(batch))
            stmt = stmt.on_conflict_do_update(
                index_elements=["source", "external_id"],
                set_={**{column: stmt.excluded[column] for column in spec.update_columns}, "updated_at": func.now()},
            ).returning(literal_column("(xmax = 0)").label("inserted"))
            for (was_inserted,) in connection.execute(stmt):
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1
    return UpsertResult(inserted, updated)
