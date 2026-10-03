"""Modelos SQLAlchemy del servicio (ver docs/contratos/modelo-datos.md).

Se completan en la Fase 4. Todo modelo debe heredar de `Base` y estar importado
aquí para que Alembic lo detecte con `alembic revision --autogenerate`.
"""

from app.db import Base

__all__ = ["Base"]
