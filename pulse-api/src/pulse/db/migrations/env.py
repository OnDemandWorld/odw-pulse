"""Alembic async migration environment.

This module is invoked by ``alembic upgrade``, ``alembic downgrade``,
``alembic check`` and similar commands.  It establishes an *async*
SQLAlchemy connection using the application ``Settings`` so that the
migration can run against a real PostgreSQL server without blocking
the event loop.

Usage (from the ``pulse-api`` root)::

    alembic upgrade head        # apply pending migrations
    alembic downgrade -1        # roll back one migration
    alembic check               # verify models are in sync with DB
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import pulse.models  # noqa: F401  (side-effect: populates Base.metadata)
from pulse.config import get_settings

# Importing ``pulse.models`` eagerly registers every model on
# ``Base.metadata`` so that autogenerate / check can compare them.
from pulse.db.base import metadata  # noqa: F401  (registers models)

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Expose the ``MetaData`` that Alembic should diff against.
target_metadata = metadata

# Override the sqlalchemy.url with the runtime settings value.
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.  The
    scripts can be reviewed and then applied manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Shared implementation for online migration execution."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a transaction."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live async database connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
