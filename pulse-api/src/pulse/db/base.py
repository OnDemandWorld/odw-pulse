"""SQLAlchemy declarative base and model registry.

Every Pulse ORM model inherits from ``Base``.  The registry is used by
Alembic ``env.py`` so that ``target_metadata`` always reflects the full
set of declared tables — including those defined in modules that are
not directly imported from the migration script.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass  # noqa: F401


class Base(DeclarativeBase):
    """Shared declarative base for all Pulse models."""


# Convenience alias — Alembic env.py imports ``metadata`` from here.
metadata = Base.metadata
