"""Smoke tests for the Pulse ORM models.

Uses an in-memory SQLite database via ``aiosqlite`` so that the tests
run without any external dependencies.  PostgreSQL-specific features
(partitioning, RLS, server-side ``gen_random_uuid()``) are not
exercised here — they are covered by the migration test-suite against
a real Postgres instance.
"""

from __future__ import annotations

import contextlib
import functools
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg_dialect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

# ---------------------------------------------------------------------------
# SQLite type compilation for PostgreSQL-specific types
# ---------------------------------------------------------------------------

# Register SQLite-compatible compilers for JSONB and ARRAY.
# These run at DDL generation time so that ``create_all`` produces
# valid SQLite DDL for the test database.


@compiles(pg_dialect.JSONB, "sqlite")
def _compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    return "JSON"


@compiles(pg_dialect.ARRAY, "sqlite")
def _compile_array_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    return "TEXT"


# ---------------------------------------------------------------------------
# SQLite adapter registration
# ---------------------------------------------------------------------------


def _uuid_as_hex(value: uuid.UUID) -> str:
    """Adapter that stores UUID values as 32-char hex strings in SQLite."""
    return value.hex


@functools.lru_cache(maxsize=1)
def _register_sqlite_adapters() -> None:
    """Register Python → SQLite type adapters (idempotent).

    * ``uuid.UUID`` → ``str`` (hex)
    * ``list``      → ``str`` (JSON) for ARRAY columns
    """
    try:
        import aiosqlite  # noqa: F401
    except ImportError:
        pytest.skip("aiosqlite is not installed")

    from sqlite3 import register_adapter

    with contextlib.suppress(Exception):  # already registered
        register_adapter(uuid.UUID, _uuid_as_hex)

    # ARRAY columns fall back to TEXT in SQLite.  Store Python lists as
    # JSON strings so that round-tripping works.
    with contextlib.suppress(Exception):
        register_adapter(list, lambda v: json.dumps(v))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` backed by an in-memory SQLite DB.

    All tables declared in ``pulse.models`` are created before the
    session is yielded, and disposed after the test finishes.
    """
    _register_sqlite_adapters()

    # Import models so that Base.metadata is populated.
    import pulse.models  # noqa: F401  (side-effect: registers all models)
    from pulse.db.base import Base

    assert Base.metadata.tables, "No models registered — import pulse.models first"

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        # Register gen_random_uuid() for SQLite so that server_default
        # expressions referencing it do not blow up at DDL time.
        def _sqlite_gen_uuid() -> str:
            return uuid.uuid4().hex

        await conn.run_sync(
            lambda c: c.connection.create_function("gen_random_uuid", 0, _sqlite_gen_uuid)
        )
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess

    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_creation_and_query(session: AsyncSession) -> None:
    """A Workspace row can be inserted and queried back."""
    from pulse.models.workspace import Workspace

    ws = Workspace(
        id=uuid.uuid4(),
        name="Acme Corp",
        slug="acme-corp",
        settings={"locale": "en-US"},
    )
    session.add(ws)
    await session.flush()

    result = await session.execute(sa.select(Workspace).where(Workspace.id == ws.id))
    fetched = result.scalar_one()
    assert fetched is not None
    assert fetched.name == "Acme Corp"
    assert fetched.slug == "acme-corp"


@pytest.mark.asyncio
async def test_user_creation_and_query(session: AsyncSession) -> None:
    """A User row linked to a Workspace can be inserted and queried."""
    from pulse.models.user import User, UserRole
    from pulse.models.workspace import Workspace

    ws_id = uuid.uuid4()
    session.add(Workspace(id=ws_id, name="Beta Inc", slug="beta-inc"))
    await session.flush()

    user = User(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        email="jane@example.com",
        role=UserRole.EDITOR,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    result = await session.execute(sa.select(User).where(User.email == "jane@example.com"))
    fetched = result.scalar_one()
    assert fetched is not None
    assert fetched.workspace_id == ws_id
    assert fetched.role == UserRole.EDITOR
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_content_piece_creation_and_query(session: AsyncSession) -> None:
    """A ContentPiece row with FK to a Workspace can be round-tripped."""
    from pulse.models.content import ContentPiece, ContentStatus
    from pulse.models.workspace import Workspace

    ws_id = uuid.uuid4()
    session.add(Workspace(id=ws_id, name="Gamma LLC", slug="gamma-llc"))
    await session.flush()

    piece = ContentPiece(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        slug="hello-world",
        title="Hello World",
        body="First post!",
        status=ContentStatus.DRAFT,
        market_code="en-US",
    )
    session.add(piece)
    await session.flush()

    result = await session.execute(sa.select(ContentPiece).where(ContentPiece.id == piece.id))
    fetched = result.scalar_one()
    assert fetched is not None
    assert fetched.title == "Hello World"
    assert fetched.status == ContentStatus.DRAFT
    assert fetched.workspace_id == ws_id


@pytest.mark.asyncio
async def test_content_version_relationship(session: AsyncSession) -> None:
    """ContentVersion can be created and accessed via the relationship."""
    from pulse.models.content import ContentPiece, ContentStatus, ContentVersion
    from pulse.models.user import User, UserRole
    from pulse.models.workspace import Workspace

    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    piece_id = uuid.uuid4()

    session.add(Workspace(id=ws_id, name="Delta Co", slug="delta-co"))
    await session.flush()
    session.add(
        User(
            id=user_id,
            workspace_id=ws_id,
            email="author@example.com",
            role=UserRole.EDITOR,
        )
    )
    await session.flush()
    session.add(
        ContentPiece(
            id=piece_id,
            workspace_id=ws_id,
            slug="versioned-post",
            title="Versioned Post",
            status=ContentStatus.REVIEW,
        )
    )
    await session.flush()

    v1 = ContentVersion(
        id=uuid.uuid4(),
        content_piece_id=piece_id,
        version_number=1,
        body="Draft body",
        status=ContentStatus.DRAFT,
        change_note="Initial version",
        created_by=user_id,
    )
    session.add(v1)
    await session.flush()

    result = await session.execute(
        sa.select(ContentVersion).where(ContentVersion.content_piece_id == piece_id)
    )
    fetched = result.scalar_one()
    assert fetched.version_number == 1
    assert fetched.body == "Draft body"
    assert fetched.created_by == user_id


@pytest.mark.asyncio
async def test_experiment_and_variant(session: AsyncSession) -> None:
    """Experiment and ExperimentVariant can be created and linked."""
    from pulse.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
    from pulse.models.workspace import Workspace

    ws_id = uuid.uuid4()
    session.add(Workspace(id=ws_id, name="Epsilon Ltd", slug="epsilon-ltd"))
    await session.flush()

    exp_id = uuid.uuid4()
    session.add(
        Experiment(
            id=exp_id,
            workspace_id=ws_id,
            name="CTA Test",
            status=ExperimentStatus.DRAFT,
            hypothesis="Shorter CTA increases CTR",
        )
    )
    await session.flush()

    session.add(
        ExperimentVariant(
            id=uuid.uuid4(),
            experiment_id=exp_id,
            name="control",
            weight=1.0,
            position=0,
        )
    )
    session.add(
        ExperimentVariant(
            id=uuid.uuid4(),
            experiment_id=exp_id,
            name="treatment",
            weight=1.0,
            position=1,
        )
    )
    await session.flush()

    result = await session.execute(
        sa.select(ExperimentVariant)
        .where(ExperimentVariant.experiment_id == exp_id)
        .order_by(ExperimentVariant.position)
    )
    variants = result.scalars().all()
    assert len(variants) == 2
    assert variants[0].name == "control"
    assert variants[1].name == "treatment"
