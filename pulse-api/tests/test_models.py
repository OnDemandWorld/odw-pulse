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
        workspace_id=ws_id,
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


# ---------------------------------------------------------------------------
# Regression: audit #3 — partition keys must be part of PKs / child FKs
# ---------------------------------------------------------------------------


def test_partitioned_tables_include_partition_key_in_pk() -> None:
    """PostgreSQL requires the partition key in every PK on partitioned tables."""
    from pulse.models.audit_log import AuditLog
    from pulse.models.content import ContentPiece, ContentVersion, ReviewAnnotation
    from pulse.models.performance_event import (
        ExperimentAssignment,
        ExperimentExposure,
        PerformanceEvent,
    )

    expectations = [
        (ContentPiece, "workspace_id"),
        (AuditLog, "created_at"),
        (ExperimentAssignment, "assigned_at"),
        (ExperimentExposure, "exposed_at"),
        (PerformanceEvent, "received_at"),
    ]
    for model, partition_col in expectations:
        pk_cols = {c.name for c in model.__table__.primary_key.columns}
        assert partition_col in pk_cols, (
            f"{model.__tablename__} PK {pk_cols} missing partition key {partition_col}"
        )

    # Children referencing the HASH-partitioned content_pieces must use
    # composite FKs (id, workspace_id).
    for child in (ContentVersion, ReviewAnnotation, PerformanceEvent):
        fks = [
            fk
            for fk in child.__table__.foreign_keys
            if fk.column.table.name == "content_pieces"
        ]
        assert fks, f"{child.__tablename__} has no FK to content_pieces"
        for fk in fks:
            assert fk.parent.name in ("content_piece_id", "workspace_id")
            constrained = {c.name for c in fk.constraint.columns}
            assert constrained == {"content_piece_id", "workspace_id"}, (
                f"{child.__tablename__} FK must be composite, got {constrained}"
            )


def test_migration_enum_and_jsonb_match_models() -> None:
    """Drift guard (audit #21/#22): migration 001 must include 'paused' and use JSONB."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src/pulse/db/migrations/versions/001_initial_schema.py"
    text = src.read_text()
    enum_block = text.split("bulk_job_status = sa.Enum(")[1].split(")")[0]
    assert '"paused"' in enum_block
    assert "sa.JSON" not in text, "migration must use postgresql.JSONB to match ORM models"


def test_admin_factory_requires_distinct_url_when_rls_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit #25: fail fast instead of silently breaking auth after RLS rollout."""
    import pulse.db.session as session_mod
    from pulse.config import Settings

    monkeypatch.setattr(session_mod, "_admin_session_factory", None)
    monkeypatch.setattr(session_mod, "_admin_engine", None)
    settings = Settings(
        rls_enforced=True,
        database_admin_url=None,
        database_url="postgresql+asyncpg://pulse:pulse@localhost/pulse",
    )
    with pytest.raises(RuntimeError, match="BYPASSRLS"):
        session_mod.get_admin_session_factory(settings)


def test_migration_rls_and_default_partitions_cover_telemetry() -> None:
    """Drift guard (audit #23/#24)."""
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "src/pulse/db/migrations/versions"
    text001 = (versions / "001_initial_schema.py").read_text()
    rls_list = text001.split("workspace_scoped_tables = [")[1].split("]")[0]
    assert '"performance_events"' in rls_list
    assert "_default PARTITION OF" in text001
    text002 = (versions / "002_user_auth.py").read_text()
    assert '"performance_events"' in text002


def test_user_and_workspace_constraints_match_migrations() -> None:
    """Drift guard (audit #61/#62)."""
    from pulse.models.user import User
    from pulse.models.workspace import Workspace

    user_uniques = {
        c.name: [col.name for col in c.columns]
        for c in User.__table__.constraints
        if isinstance(c, sa.UniqueConstraint)
    }
    assert user_uniques.get("uq_users_email") == ["email"]
    assert "uq_users_workspace_email" not in user_uniques

    slug_col = Workspace.__table__.c.slug
    assert slug_col.unique is not True
    slug_uniques = [
        c for c in Workspace.__table__.constraints
        if isinstance(c, sa.UniqueConstraint) and "slug" in [col.name for col in c.columns]
    ]
    assert len(slug_uniques) == 1
    assert slug_uniques[0].name == "uq_workspaces_slug"


def test_alembic_env_escapes_percent_in_url() -> None:
    """Drift guard (audit #65): ConfigParser interpolation requires %%."""
    from pathlib import Path

    env_py = Path(__file__).resolve().parents[1] / "src/pulse/db/migrations/env.py"
    assert '.replace("%", "%%")' in env_py.read_text()
