"""Health endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from pulse.main import app


@pytest.mark.anyio
async def test_liveness() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    # Engine uninitialized (fresh process) -> readiness ok. Other tests in
    # this process may have created the global engine; isolate it.
    import pulse.db.session as session_mod

    monkeypatch.setattr(session_mod, "_engine", None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_api_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Regression: audit #75/#100 — readiness reflects DB; CORS outermost
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_readiness_503_when_db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    import pulse.db.session as session_mod
    from pulse.main import app

    class _DeadEngine:
        def connect(self):
            raise ConnectionError("db down")

    monkeypatch.setattr(session_mod, "_engine", _DeadEngine())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503


def test_cors_middleware_is_outermost() -> None:
    from fastapi.middleware.cors import CORSMiddleware

    from pulse.main import create_app

    app = create_app()
    assert app.user_middleware[0].cls is CORSMiddleware
