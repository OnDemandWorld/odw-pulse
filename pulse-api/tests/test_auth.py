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
    authorized_client: AsyncClient,
    test_workspace_and_user,
) -> None:
    """A token scoped to workspace B cannot read workspace A's resources.

    Audit finding #41: the previous version only checked that /me echoes
    each token's own workspace — it never attempted cross-workspace access.
    This version creates a real resource in workspace A and requests it
    with a workspace-B token (same user id, different workspace claim).
    """
    # Create a resource in workspace A (the fixture workspace).
    response = await authorized_client.post(
        "/api/v1/content",
        json={"slug": "isolation-probe", "title": "Workspace A secret"},
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    workspace_b = uuid.UUID("00000000-0000-0000-0000-000000000099")
    token_b = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=workspace_b,
        role="owner",
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Direct fetch of A's resource with B's token must 404.
    response = await client.get(f"/api/v1/content/{content_id}", headers=headers_b)
    assert response.status_code == 404

    # Listing with B's token must not leak A's items.
    response = await client.get("/api/v1/content", headers=headers_b)
    assert response.status_code == 200
    assert all(item["id"] != content_id for item in response.json()["items"])


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

    # Negative path (audit finding #76): the viewer must get 403 on both
    # user-management endpoints, not just the owner getting 200.
    login = await authorized_client.post(
        "/api/v1/auth/login",
        json={"username": "viewer@example.com", "password": "viewerpass123"},
    )
    assert login.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await authorized_client.get("/api/v1/auth/users", headers=viewer_headers)
    assert response.status_code == 403
    response = await authorized_client.post(
        "/api/v1/auth/users",
        json={"email": "another@example.com", "password": "password123", "role": "viewer"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


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


# ---------------------------------------------------------------------------
# Regression: audit #11 — impersonation must not cross workspace membership
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_impersonate_foreign_workspace_forbidden(
    async_session, authorized_client: AsyncClient, test_workspace_and_user
) -> None:
    """An owner cannot mint a token for a workspace they do not belong to."""
    from pulse.models.workspace import Workspace

    other = Workspace(
        id=uuid.uuid4(), name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}"
    )
    async_session.add(other)
    await async_session.commit()

    response = await authorized_client.post(
        "/api/v1/auth/impersonate",
        json={"target_workspace_id": str(other.id)},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Regression: audit #51/#52/#53/#56 — auth & API hardening
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_register_rejects_overlong_password(client: AsyncClient) -> None:
    """bcrypt 5.x raises on >72 bytes; the API must return 422, not 500."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "workspace_name": "Long PW Co",
            "email": "longpw@example.com",
            "password": "x" * 73,
        },
    )
    assert response.status_code == 422


def test_client_ip_ignores_spoofed_xff_from_untrusted_peer() -> None:
    from types import SimpleNamespace

    from pulse.api.ratelimit import client_ip

    # Direct public connection: spoofed header must be ignored.
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4"},
        client=SimpleNamespace(host="203.0.113.9"),
    )
    assert client_ip(req) == "203.0.113.9"  # type: ignore[arg-type]

    # Behind a trusted (private) proxy: rightmost untrusted entry wins.
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 198.51.100.7"},
        client=SimpleNamespace(host="172.18.0.5"),
    )
    assert client_ip(req) == "198.51.100.7"  # type: ignore[arg-type]


def test_default_secrets_replaced_outside_production() -> None:
    from pulse.config import get_settings
    from pulse.main import create_app

    create_app()
    settings = get_settings()
    assert settings.pulse_secret_key != "change-me-in-production"
    assert settings.webhook_signing_secret != "whsec_change_me"


@pytest.mark.anyio
async def test_viewer_role_cannot_write_content(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Viewers may read but not create content (audit #56)."""
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="viewer",
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/api/v1/content",
        json={"slug": "viewer-post", "title": "Nope"},
        headers=headers,
    )
    assert response.status_code == 403

    response = await client.get("/api/v1/content", headers=headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Regression: audit #95/#96 — fail-closed validation and clean 401s
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_missing_column_error_does_not_fail_open(
    client: AsyncClient, test_workspace_and_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing COLUMN (partial migration) must 503, not skip validation."""
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _boom(self, *args, **kwargs):
        raise ProgrammingError(
            "SELECT ...", None, Exception("column users.is_active does not exist")
        )

    monkeypatch.setattr(AsyncSession, "execute", _boom)
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="owner",
    )
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_missing_users_table_still_fails_open(
    client: AsyncClient, test_workspace_and_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The genuine undefined-table case keeps the pre-migration behavior."""
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.ext.asyncio import AsyncSession

    async def _boom(self, *args, **kwargs):
        raise ProgrammingError("SELECT ...", None, Exception("no such table: users"))

    monkeypatch.setattr(AsyncSession, "execute", _boom)
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="owner",
    )
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_token_missing_claims_returns_401(
    client: AsyncClient, test_workspace_and_user
) -> None:
    from jose import jwt

    from pulse.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {"sub": str(TEST_USER_ID), "email": TEST_EMAIL, "role": "owner"},
        settings.pulse_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
