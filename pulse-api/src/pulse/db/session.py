"""Async SQLAlchemy session factory.

Usage (inside a FastAPI request)::

    from pulse.db.session import get_session_factory

    async with get_session_factory() as session:
        ...

For production the *database_url* comes from ``Settings``; tests can
override it freely.

Row-Level Security context
--------------------------
Every transaction opened on PostgreSQL has ``pulse.workspace_id`` set via
``SET LOCAL`` (see :func:`_apply_workspace_rls`).  The value is taken from
the request-scoped :class:`~pulse.auth.dependencies.WorkspaceContext`, which
``get_current_user`` populates from the verified JWT.  Because ``SET LOCAL``
only lasts for its transaction, the hook re-applies it on every new
transaction the session begins (including after commits).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

from pulse.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Privileged engine used for pre-authentication lookups (login,
# registration).  Separate because the RLS-scoped application role cannot
# read users without a workspace context.
_admin_engine: AsyncEngine | None = None
_admin_session_factory: async_sessionmaker[AsyncSession] | None = None


# ---------------------------------------------------------------------------
# RLS context hook — re-applies the workspace setting on every transaction.
# ---------------------------------------------------------------------------


@event.listens_for(Session, "after_begin")
def _apply_workspace_rls(session: Session, transaction: Any, connection: Connection) -> None:
    """Issue ``SET LOCAL pulse.workspace_id`` at the start of each transaction.

    Skipped for non-PostgreSQL dialects (tests on SQLite) and for requests
    without an authenticated workspace (public endpoints, workers).
    """
    del session, transaction  # unused
    if connection.dialect.name != "postgresql":
        return
    # Imported lazily: auth.dependencies imports this module for get_db.
    from pulse.auth.dependencies import WorkspaceContext

    workspace_id = WorkspaceContext.get()
    if workspace_id is None:
        return
    connection.execute(
        text("SET LOCAL pulse.workspace_id = :wid"),
        {"wid": str(workspace_id)},
    )


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------


def _get_or_create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return a cached async engine, creating it on first call."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        s = settings or get_settings()
        _engine = create_async_engine(
            s.database_url,
            pool_size=s.database_pool_size,
            max_overflow=s.database_max_overflow,
            echo=s.pulse_debug,
        )
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Return a cached ``async_sessionmaker`` bound to the global engine."""
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        engine = _get_or_create_engine(settings)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an ``AsyncSession`` per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def get_admin_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return a cached session factory bound to the privileged admin engine.

    Falls back to the regular database URL when ``database_admin_url`` is
    unset (single-role development setups).
    """
    global _admin_engine, _admin_session_factory  # noqa: PLW0603
    if _admin_session_factory is None:
        s = settings or get_settings()
        admin_url = s.database_admin_url or s.database_url
        _admin_engine = create_async_engine(
            admin_url,
            pool_size=s.database_pool_size,
            max_overflow=s.database_max_overflow,
            echo=s.pulse_debug,
        )
        _admin_session_factory = async_sessionmaker(_admin_engine, expire_on_commit=False)
    return _admin_session_factory


async def get_admin_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — privileged session for pre-auth endpoints."""
    factory = get_admin_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the global engines (call on application shutdown)."""
    global _engine, _session_factory  # noqa: PLW0603
    global _admin_engine, _admin_session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    if _admin_engine is not None:
        await _admin_engine.dispose()
        _admin_engine = None
        _admin_session_factory = None
