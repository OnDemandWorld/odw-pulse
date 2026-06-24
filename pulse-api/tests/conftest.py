"""Shared pytest fixtures for the Pulse test suite."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Register JSONB → JSON compiler for SQLite so all tables can be created.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

from pulse.api.v1.auth import _MOCK_EMAIL, _MOCK_WORKSPACE_ID
from pulse.auth.security import create_access_token


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element: Any, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    """Render PostgreSQL JSONB columns as JSON on SQLite."""
    return "JSON"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(element: Any, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    """Render PostgreSQL ARRAY columns as JSON on SQLite."""
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element: Any, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    """Render PostgreSQL UUID columns as VARCHAR on SQLite."""
    return "VARCHAR(36)"


# Import content models so they're registered with Base.metadata.
from pulse.models.bulk_job import BulkJob  # noqa: E402, F401
from pulse.models.content import ContentPiece, ContentVersion, ReviewAnnotation  # noqa: E402, F401
from pulse.models.user import User  # noqa: E402, F401
from pulse.models.webhook_config import WebhookConfig  # noqa: E402, F401
from pulse.models.workspace import Workspace  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Event-loop fixture for pytest-asyncio
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Any:
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Async engine & session fixtures (in-memory SQLite)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_engine() -> AsyncGenerator[Any, None]:
    """Return an async engine backed by in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Register gen_random_uuid() function for SQLite
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ARG001
        """Register PostgreSQL-compatible functions for SQLite."""
        dbapi_connection.create_function(
            "gen_random_uuid", 0, lambda: str(uuid.uuid4())
        )

    # Create all tables for in-memory testing.
    from pulse.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session bound to the in-memory engine."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# DB session fixture (alias for backward compatibility)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(async_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Alias for ``async_session`` for tests that name the fixture ``db_session``."""
    yield async_session


# ---------------------------------------------------------------------------
# FastAPI test client fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(app_fixture: Any) -> AsyncGenerator[AsyncClient, None]:
    """Return an ``AsyncClient`` wired to the test FastAPI app."""
    transport = ASGITransport(app=app_fixture)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def authorized_client(app_fixture: Any) -> AsyncGenerator[AsyncClient, None]:
    """Return an ``AsyncClient`` with a valid JWT in the Authorization header."""
    token = create_access_token(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email=_MOCK_EMAIL,
        workspace_id=_MOCK_WORKSPACE_ID,
        role="admin",
    )
    transport = ASGITransport(app=app_fixture)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# App fixture — override dependencies so that the real DB engine is not used
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_fixture(async_session: AsyncSession) -> Any:
    """Yield a FastAPI app with the DB dependency overridden for tests."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from pulse.api import health
    from pulse.api.v1 import auth as auth_v1
    from pulse.api.v1 import bulk_jobs as bulk_jobs_v1
    from pulse.api.v1 import content as content_v1
    from pulse.api.v1 import integrations as integrations_v1
    from pulse.middleware.tenant import TenantMiddleware

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantMiddleware)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth_v1.router, prefix="/api/v1")
    app.include_router(content_v1.router, prefix="/api/v1")
    app.include_router(bulk_jobs_v1.router, prefix="/api/v1")
    app.include_router(integrations_v1.router, prefix="/api/v1")

    # Override the DB dependency so endpoints use the in-memory session.
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    app.dependency_overrides[auth_v1.get_db] = _override_get_db
    app.dependency_overrides[content_v1.get_db] = _override_get_db
    app.dependency_overrides[bulk_jobs_v1.get_db] = _override_get_db
    app.dependency_overrides[integrations_v1.get_db] = _override_get_db  # type: ignore[attr-defined]

    yield app

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Workspace + User fixtures for content tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_workspace_and_user(async_session: AsyncSession) -> tuple[Any, Any]:
    """Create a workspace and user matching the mock JWT token IDs."""
    from pulse.api.v1.auth import _MOCK_USER_ID, _MOCK_WORKSPACE_ID
    from pulse.models.user import UserRole

    workspace = Workspace(
        id=_MOCK_WORKSPACE_ID,
        name="Test Workspace",
        slug="test-workspace",
    )
    async_session.add(workspace)

    user = User(
        id=_MOCK_USER_ID,
        workspace_id=_MOCK_WORKSPACE_ID,
        email="test@example.com",
        role=UserRole.ADMIN,
        is_active=True,
    )
    async_session.add(user)
    await async_session.commit()

    return workspace, user
