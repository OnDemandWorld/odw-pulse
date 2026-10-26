"""Auth hardening tests: rate limiting (C-3) and token revocation (C-4).

The autouse ``_isolate_kv_store`` fixture pins the shared KV store to its
in-process fallback and clears it between tests, so the counters here are
deterministic and never touch a running Redis.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from pulse.auth.security import create_access_token, decode_access_token
from pulse.core.redis_kv import RedisKV
from tests.conftest import TEST_EMAIL, TEST_PASSWORD, TEST_USER_ID, TEST_WORKSPACE_ID

_LOGIN = "/api/v1/auth/login"
_REGISTER = "/api/v1/auth/register"
_LOGOUT = "/api/v1/auth/logout"
_ME = "/api/v1/auth/me"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /auth/login — brute-force throttle (RATE_LIMIT_LOGIN_PER_MINUTE = 5)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_login_rate_limited_after_burst(client: AsyncClient, test_workspace_and_user) -> None:
    """Attempts beyond the per-minute limit get 429 + Retry-After."""
    for _ in range(5):
        response = await client.post(
            _LOGIN, json={"username": "nobody@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401  # throttled *after* the limit is reached

    response = await client.post(
        _LOGIN, json={"username": "nobody@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert int(response.headers["retry-after"]) >= 1

    # While limited, even correct credentials are throttled.
    response = await client.post(
        _LOGIN, json={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 429


@pytest.mark.anyio
async def test_register_rate_limit_is_a_separate_scope(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Hitting the register limit (3/min) does not throttle login."""
    for _ in range(3):
        response = await client.post(
            _REGISTER,
            json={"workspace_name": "Farm", "email": TEST_EMAIL, "password": "somepassword"},
        )
        assert response.status_code != 429  # duplicate email → 409, but still counted

    response = await client.post(
        _REGISTER,
        json={"workspace_name": "Farm", "email": TEST_EMAIL, "password": "somepassword"},
    )
    assert response.status_code == 429

    response = await client.post(
        _LOGIN, json={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200  # separate counter scope


@pytest.mark.anyio
async def test_rate_limit_can_be_disabled(
    client: AsyncClient, test_workspace_and_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RATE_LIMIT_ENABLED=false restores unlimited login attempts."""
    from pulse.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    for _ in range(7):
        response = await client.post(
            _LOGIN, json={"username": "nobody@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout — per-token server-side revocation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_access_tokens_carry_jti() -> None:
    """Every token gets a unique id so logout can blocklist exactly one."""
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="owner",
    )
    payload = decode_access_token(token)
    assert payload.get("jti")


@pytest.mark.anyio
async def test_logout_revokes_the_presented_token(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """After /auth/logout the token is dead server-side, not just client-side."""
    token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="owner",
    )
    assert (await client.get(_ME, headers=_auth_header(token))).status_code == 200

    response = await client.post(_LOGOUT, headers=_auth_header(token))
    assert response.status_code == 200

    response = await client.get(_ME, headers=_auth_header(token))
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"]


@pytest.mark.anyio
async def test_logout_does_not_affect_other_sessions(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Revoking one token must not invalidate a different session's token."""
    token_a = create_access_token(
        user_id=TEST_USER_ID, email=TEST_EMAIL, workspace_id=TEST_WORKSPACE_ID, role="owner"
    )
    token_b = create_access_token(
        user_id=TEST_USER_ID, email=TEST_EMAIL, workspace_id=TEST_WORKSPACE_ID, role="owner"
    )
    await client.post(_LOGOUT, headers=_auth_header(token_a))

    assert (await client.get(_ME, headers=_auth_header(token_a))).status_code == 401
    assert (await client.get(_ME, headers=_auth_header(token_b))).status_code == 200


@pytest.mark.anyio
async def test_logout_requires_authentication(client: AsyncClient) -> None:
    """Anonymous logout is a 401 like every other protected endpoint."""
    response = await client.post(_LOGOUT)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout-everywhere — per-user iat cutoff
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_logout_everywhere_revokes_existing_sessions(
    client: AsyncClient, test_workspace_and_user
) -> None:
    """Old tokens die across the board, but a fresh login after the cutoff works."""
    old_token = create_access_token(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        workspace_id=TEST_WORKSPACE_ID,
        role="owner",
    )
    assert (await client.get(_ME, headers=_auth_header(old_token))).status_code == 200

    response = await client.post(
        "/api/v1/auth/logout-everywhere", headers=_auth_header(old_token)
    )
    assert response.status_code == 200

    assert (await client.get(_ME, headers=_auth_header(old_token))).status_code == 401

    # iat has second granularity, so tokens minted after the next boundary
    # are unaffected — wait it out and log in again.
    await asyncio.sleep(1.05)
    response = await client.post(
        _LOGIN, json={"username": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert (await client.get(_ME, headers=_auth_header(new_token))).status_code == 200


# ---------------------------------------------------------------------------
# KV store fallback unit behaviour
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_kv_store_local_fallback_counts_and_expires() -> None:
    """With Redis short-circuited, windows count per key and values expire."""
    store = RedisKV(redis_url="redis://127.0.0.1:1/0")
    store.use_local_only()

    counts = [await store.incr("k", 60) for _ in range(3)]
    assert [count for count, _ in counts] == [1, 2, 3]
    assert counts[0][1] >= 1  # retry-after always present

    # Independent key.
    assert (await store.incr("other", 60))[0] == 1

    await store.set("v", "x", 60)
    assert await store.get("v") == "x"
    assert await store.get("absent") is None

    # A zero-second TTL expires immediately on the local fallback.
    await store.set("v2", "y", 0)
    assert await store.get("v2") is None
