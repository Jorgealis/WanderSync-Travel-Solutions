from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


async def insert_or_get(
    session: AsyncSession,
    model: type[ModelT],
    values: dict[str, Any],
    conflict_columns: Sequence[str],
) -> tuple[ModelT, bool]:
    """Inserta una fila o devuelve la existente si choca con una restricción UNIQUE.

    Devuelve (fila, creada). Es la base de las operaciones idempotentes: por ejemplo,
    una reserva con un saga_id ya registrado devuelve la reserva original en lugar de
    crear otra. Usa INSERT ... ON CONFLICT DO NOTHING, que es seguro ante peticiones
    concurrentes (a diferencia de "SELECT y luego INSERT").

    `conflict_columns` debe corresponder a una restricción UNIQUE de la tabla.
    No hace commit: la transacción la controla quien llama.
    """
    stmt = (
        insert(model)
        .values(**values)
        .on_conflict_do_nothing(index_elements=list(conflict_columns))
        .returning(model)
    )
    created = (await session.scalars(stmt)).one_or_none()
    if created is not None:
        return created, True

    filters = [getattr(model, column) == values[column] for column in conflict_columns]
    existing = (await session.scalars(select(model).where(*filters))).one()
    return existing, False
