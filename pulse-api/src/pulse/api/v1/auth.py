"""Authentication endpoints (TSD §2.7).

* ``POST /auth/login``         — exchange credentials for a JWT
* ``GET  /auth/me``            — return the current user's identity
* ``POST /auth/impersonate``   — switch workspace context (admin only)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.auth.models import ImpersonateRequest, LoginRequest, TokenResponse
from pulse.auth.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Mock user store — will be replaced by real DB queries once user management
# is implemented.  The mock lets us develop and test the full auth flow
# without provisioning a real user table.
# ---------------------------------------------------------------------------
_MOCK_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_MOCK_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_MOCK_EMAIL = "test@example.com"
_MOCK_PASSWORD_HASH = hash_password("testpassword")
_MOCK_ROLE = "admin"


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    _session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username/password and receive a JWT access token."""
    # Mock authentication: accept the hardcoded test user.
    if body.username == _MOCK_EMAIL and verify_password(body.password, _MOCK_PASSWORD_HASH):
        token = create_access_token(
            user_id=_MOCK_USER_ID,
            email=_MOCK_EMAIL,
            workspace_id=_MOCK_WORKSPACE_ID,
            role=_MOCK_ROLE,
        )
        return TokenResponse(access_token=token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=dict[str, str])
async def me(
    current_user: CurrentUser,
) -> dict[str, str]:
    """Return information about the currently authenticated user."""
    return {
        "id": str(current_user.user_id),
        "email": current_user.email,
        "role": current_user.role,
        "workspace_id": str(current_user.workspace_id),
    }


# ---------------------------------------------------------------------------
# POST /auth/impersonate
# ---------------------------------------------------------------------------


@router.post("/impersonate", response_model=TokenResponse)
async def impersonate(
    body: ImpersonateRequest,
    current_user: CurrentUser,
) -> TokenResponse:
    """Issue a new token scoped to *target_workspace_id* (admin only)."""
    if current_user.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can impersonate",
        )
    token = create_access_token(
        user_id=current_user.user_id,
        email=current_user.email,
        workspace_id=body.target_workspace_id,
        role=current_user.role,
    )
    return TokenResponse(access_token=token)
