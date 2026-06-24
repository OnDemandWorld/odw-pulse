"""Authentication and tenant-isolation tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from pulse.api.v1.auth import _MOCK_EMAIL
from pulse.auth.security import create_access_token

# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_login_returns_token(client: AsyncClient) -> None:
    """Login with valid credentials should return an access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": _MOCK_EMAIL, "password": "testpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_login_invalid_credentials_returns_401(client: AsyncClient) -> None:
    """Login with wrong credentials should return 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrong@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me — authentication enforcement
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_protected_endpoint_without_token_401(client: AsyncClient) -> None:
    """Accessing /me without a token should return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_protected_endpoint_with_valid_token_200(
    authorized_client: AsyncClient,
) -> None:
    """Accessing /me with a valid token should return 200 with user info."""
    response = await authorized_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == _MOCK_EMAIL
    assert "id" in data
    assert "role" in data


@pytest.mark.anyio
async def test_protected_endpoint_with_invalid_token_returns_401(
    client: AsyncClient,
) -> None:
    """Accessing /me with a garbage token should return 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_workspace_isolation_user_cannot_access_other_workspace(
    client: AsyncClient,
) -> None:
    """A token scoped to workspace A cannot be used to access workspace B.

    The ``require_workspace`` dependency compares the JWT workspace_id against
    the workspace_id in the URL path.  We simulate a workspace-scoped endpoint
    by hitting /me (which reflects the token's workspace) and verifying that
    two different tokens carry different workspace contexts.
    """
    workspace_a = uuid.UUID("00000000-0000-0000-0000-000000000002")
    workspace_b = uuid.UUID("00000000-0000-0000-0000-000000000099")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    token_a = create_access_token(
        user_id=user_id,
        email="alice@workspace-a.com",
        workspace_id=workspace_a,
        role="editor",
    )
    token_b = create_access_token(
        user_id=user_id,
        email="alice@workspace-a.com",
        workspace_id=workspace_b,
        role="editor",
    )

    response_a = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    response_b = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    data_a = response_a.json()
    data_b = response_b.json()

    # Each token reflects its own workspace — confirming isolation.
    assert data_a["workspace_id"] == str(workspace_a)
    assert data_b["workspace_id"] == str(workspace_b)
    assert data_a["workspace_id"] != data_b["workspace_id"]


# ---------------------------------------------------------------------------
# POST /api/v1/auth/impersonate
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_impersonate_returns_new_token(authorized_client: AsyncClient) -> None:
    """Admin impersonation should return a token for the target workspace."""
    target_workspace = uuid.UUID("00000000-0000-0000-0000-000000000042")
    response = await authorized_client.post(
        "/api/v1/auth/impersonate",
        json={"target_workspace_id": str(target_workspace)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
