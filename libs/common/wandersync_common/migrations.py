"""Helpers para las migraciones Alembic de los servicios de catálogo.

Implementa la "Matriz de privilegios" de docs/contratos/modelo-datos.md:
- `ingest` (Dask) puede leer e insertar ofertas, pero solo ACTUALIZAR las columnas de
  precio y metadata. El inventario (seats/rooms/units) queda fuera: aunque el código de
  la ingesta tuviera un error, Postgres rechazaría modificarlo.
- `hasura_ro` solo puede leer la tabla de ofertas (nunca las reservas).

Los nombres de los roles vienen de las variables INGEST_DB_USER y HASURA_RO_DB_USER.
"""

import os
from collections.abc import Sequence

from alembic import op


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _roles() -> tuple[str, str]:
    ingest = os.environ.get("INGEST_DB_USER")
    hasura = os.environ.get("HASURA_RO_DB_USER")
    if not ingest or not hasura:
        raise RuntimeError("La migración necesita INGEST_DB_USER y HASURA_RO_DB_USER en el entorno")
    return _quote(ingest), _quote(hasura)


def grant_catalog_access(schema: str, table: str, ingest_update_columns: Sequence[str]) -> None:
    ingest, hasura = _roles()
    qualified = f"{_quote(schema)}.{_quote(table)}"
    columns = ", ".join(_quote(c) for c in ingest_update_columns)
    op.execute(f"GRANT SELECT, INSERT ON {qualified} TO {ingest}")
    op.execute(f"GRANT UPDATE ({columns}) ON {qualified} TO {ingest}")
    op.execute(f"GRANT SELECT ON {qualified} TO {hasura}")


def revoke_catalog_access(schema: str, table: str) -> None:
    ingest, hasura = _roles()
    qualified = f"{_quote(schema)}.{_quote(table)}"
    op.execute(f"REVOKE ALL ON {qualified} FROM {ingest}, {hasura}")
