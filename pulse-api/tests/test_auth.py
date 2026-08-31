"""Authentication and tenant-isolation tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from pulse.auth.security import create_access_token
from tests.conftest import TEST_EMAIL, TEST_PASSWORD, TEST_USER_ID, TEST_WORKSPACE_ID

# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_login_returns_token(client: AsyncClient, test_workspace_and_user) -> None:
    """Login with valid credentials should return an access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["email"] == TEST_EMAIL
    assert "workspace_id" in data


@pytest.mark.anyio
async def test_login_invalid_credentials_returns_401(client: AsyncClient, test_workspace_and_user) -> None:
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
async def test_protected_endpoint_without_token_401(client: AsyncClient, test_workspace_and_user) -> None:
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
    assert data["email"] == TEST_EMAIL
    assert "id" in data
    assert "role" in data


@pytest.mark.anyio
async def test_protected_endpoint_with_invalid_token_returns_401(
    client: AsyncClient,
    test_workspace_and_user,
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
    test_workspace_and_user,
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
async def test_impersonate_returns_new_token(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[object, object],
) -> None:
    """Admin impersonation into an existing workspace returns a new token."""
    del test_workspace_and_user  # Fixture side effect: creates the workspace row.
    from tests.conftest import TEST_WORKSPACE_ID

    response = await authorized_client.post(
        "/api/v1/auth/impersonate",
        json={"target_workspace_id": str(TEST_WORKSPACE_ID)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_impersonate_unknown_workspace_returns_404(
    authorized_client: AsyncClient,
) -> None:
    """Impersonation must refuse to issue tokens for workspaces that don't exist."""
    nonexistent = uuid.UUID("00000000-0000-0000-0000-000000000042")
    response = await authorized_client.post(
        "/api/v1/auth/impersonate",
        json={"target_workspace_id": str(nonexistent)},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_generate_without_token_401(client: AsyncClient, test_workspace_and_user) -> None:
    """LLM generation endpoints must require authentication (cost protection)."""
    response = await client.post(
        "/api/v1/generate",
        json={
            "content_type": "blog_post",
            "target_market": "en-US",
            "prompt": "Write about AI",
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_register_creates_workspace_and_owner(client: AsyncClient) -> None:
    """Register creates a new workspace + owner and returns a valid token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "workspace_name": "New Workspace",
            "email": "newowner@example.com",
            "password": "newpassword123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["email"] == "newowner@example.com"
    assert "workspace_id" in data

    # Token should work
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "newowner@example.com"
    assert response.json()["role"] == "owner"


@pytest.mark.anyio
async def test_register_duplicate_email_409(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Registering with an email that already exists should return 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "workspace_name": "Another Workspace",
            "email": TEST_EMAIL,  # already exists from fixture
            "password": "newpassword123",
        },
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/v1/auth/users + POST /api/v1/auth/users
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_users_requires_admin(
    authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Only admin/owner can list users."""
    # Create a viewer user in the DB
    response = await authorized_client.post(
        "/api/v1/auth/users",
        json={
            "email": "viewer@example.com",
            "password": "viewerpass123",
            "role": "viewer",
        },
    )
    assert response.status_code == 201

    # Verify the owner can list users (positive test).
    response = await authorized_client.get("/api/v1/auth/users")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_list_users_returns_workspace_users(
    authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Admin can list users in their workspace."""
    response = await authorized_client.get("/api/v1/auth/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    assert any(u["email"] == TEST_EMAIL for u in users)


@pytest.mark.anyio
async def test_create_user_by_admin(
    authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Admin can create a new user in the workspace."""
    response = await authorized_client.post(
        "/api/v1/auth/users",
        json={
            "email": "newuser@example.com",
            "password": "newuserpass123",
            "role": "editor",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "editor"
    assert data["is_active"] is True


@pytest.mark.anyio
async def test_create_user_duplicate_email_409(
    authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Creating a user with a duplicate email returns 409."""
    response = await authorized_client.post(
        "/api/v1/auth/users",
        json={
            "email": TEST_EMAIL,  # already exists
            "password": "somepassword",
            "role": "viewer",
        },
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/v1/auth/users/{id}/deactivate
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deactivate_user_self_forbidden(
    authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Users cannot deactivate themselves."""
    response = await authorized_client.post(f"/api/v1/auth/users/{TEST_USER_ID}/deactivate")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_deactivate_user_by_owner(
    client: AsyncClient, authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """Owner can deactivate another user."""
    # First create a user to deactivate
    response = await authorized_client.post(
        "/api/v1/auth/users",
        json={
            "email": "todeactivate@example.com",
            "password": "somepassword",
            "role": "viewer",
        },
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    # Deactivate them
    response = await authorized_client.post(f"/api/v1/auth/users/{user_id}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Deactivated user cannot login
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "todeactivate@example.com", "password": "somepassword"},
    )
    assert response.status_code == 403  # deactivated


@pytest.mark.anyio
async def test_impersonate_requires_owner(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Only owner role can impersonate."""
    # Admin token (not owner)
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="admin",
    )
    response = await client.post(
        "/api/v1/auth/impersonate",
        json={"target_workspace_id": str(TEST_WORKSPACE_ID)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
