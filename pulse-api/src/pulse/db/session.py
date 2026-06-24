"""Async SQLAlchemy session factory.

Usage (inside a FastAPI request)::

    from pulse.db.session import get_session_factory

    async with get_session_factory() as session:
        ...

For production the *database_url* comes from ``Settings``; tests can
override it freely.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pulse.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


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


async def dispose_engine() -> None:
    """Dispose the global engine (call on application shutdown)."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
