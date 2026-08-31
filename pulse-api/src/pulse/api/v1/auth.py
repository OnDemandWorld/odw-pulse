"""Authentication endpoints (TSD §2.7).

* ``POST /auth/register``           — create a workspace + owner account
* ``POST /auth/login``              — exchange credentials for a JWT
* ``GET  /auth/me``                 — return the current user's identity
* ``GET  /auth/users``              — list users in the caller's workspace
* ``POST /auth/users``              — invite a user to the caller's workspace
* ``POST /auth/users/{id}/deactivate`` — deactivate a user
* ``POST /auth/impersonate``        — switch workspace context (owners only)

Login and registration run on the *privileged* database session
(``get_admin_session``): with RLS enforced, the scoped application role
cannot read ``users`` before a workspace context exists.
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.auth.models import (
    ImpersonateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from pulse.auth.security import create_access_token, hash_password, verify_password
from pulse.db.session import get_admin_session
from pulse.models.audit_log import AuditLog
from pulse.models.user import User, UserRole
from pulse.models.workspace import Workspace

router = APIRouter(prefix="/auth", tags=["auth"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _workspace_slug(name: str) -> str:
    """Derive a unique, URL-safe workspace slug from a display name."""
    slug = _SLUG_RE.sub("-", name.lower()).strip("-") or "workspace"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _check_role(current_user: object, allowed: tuple[str, ...]) -> None:
    """Raise 403 unless the caller's role is in *allowed*."""
    role = str(getattr(current_user, "role", ""))
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' is not permitted. Required: {', '.join(allowed)}",
        )


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_admin_session),
) -> TokenResponse:
    """Create a new workspace and its owner account, returning a JWT."""
    email = body.email.strip().lower()

    result = await db.execute(select(User.id).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    workspace = Workspace(
        id=uuid.uuid4(),
        name=body.workspace_name.strip(),
        slug=_workspace_slug(body.workspace_name),
    )
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        email=email,
        role=UserRole.OWNER,
        is_active=True,
        password_hash=hash_password(body.password),
    )
    db.add_all([workspace, user])
    try:
        await db.commit()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    token = create_access_token(
        user_id=user.id,
        email=email,
        workspace_id=workspace.id,
        role=UserRole.OWNER.value,
    )
    return TokenResponse(access_token=token, workspace_id=workspace.id, email=email)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_admin_session),
) -> TokenResponse:
    """Authenticate with email/password and receive a JWT access token."""
    email = body.username.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.password_hash or not verify_password(
        body.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        workspace_id=user.workspace_id,
        role=user.role.value,
    )
    return TokenResponse(access_token=token, workspace_id=user.workspace_id, email=user.email)


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
# GET /auth/users — workspace user management
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserRead])
async def list_users(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    """List all users in the caller's workspace (admin and above)."""
    _check_role(current_user, ("admin", "owner"))
    result = await db.execute(
        select(User)
        .where(User.workspace_id == current_user.workspace_id)
        .order_by(User.created_at)
    )
    return [_to_user_read(u) for u in result.scalars()]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Invite a user into the caller's workspace (admin and above).

    Only an owner may create additional owners.
    """
    _check_role(current_user, ("admin", "owner"))

    try:
        role = UserRole(body.role.lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. "
            f"Valid roles: {', '.join(r.value for r in UserRole)}",
        ) from exc

    if role is UserRole.OWNER and current_user.role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can create another owner",
        )

    email = body.email.strip().lower()
    existing = await db.execute(select(User.id).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        id=uuid.uuid4(),
        workspace_id=current_user.workspace_id,
        email=email,
        role=role,
        is_active=True,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            workspace_id=current_user.workspace_id,
            action="user.created",
            actor_id=current_user.user_id,
            resource=f"user:{user.id}",
            details={"email": email, "role": role.value},
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    await db.refresh(user)
    return _to_user_read(user)


@router.post("/users/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Deactivate a user in the caller's workspace (admin and above).

    Deactivated users keep their data but can no longer authenticate.
    Owners can only be deactivated by an owner, and nobody can deactivate
    themselves.
    """
    _check_role(current_user, ("admin", "owner"))

    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.workspace_id == current_user.workspace_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.role is UserRole.OWNER and current_user.role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can deactivate an owner",
        )

    user.is_active = False
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            workspace_id=current_user.workspace_id,
            action="user.deactivated",
            actor_id=current_user.user_id,
            resource=f"user:{user.id}",
            details={"email": user.email},
        )
    )
    await db.commit()
    await db.refresh(user)
    return _to_user_read(user)


# ---------------------------------------------------------------------------
# POST /auth/impersonate
# ---------------------------------------------------------------------------


@router.post("/impersonate", response_model=TokenResponse)
async def impersonate(
    body: ImpersonateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue a new token scoped to *target_workspace_id* (owners only).

    The target workspace must exist.  The action is recorded in the audit
    log.  TODO: once cross-workspace membership exists, verify the caller
    actually administers the target workspace.
    """
    if current_user.role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can impersonate",
        )

    result = await db.execute(
        select(Workspace.id).where(Workspace.id == body.target_workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target workspace does not exist",
        )

    db.add(
        AuditLog(
            id=uuid.uuid4(),
            workspace_id=current_user.workspace_id,
            action="auth.impersonate",
            actor_id=current_user.user_id,
            resource=f"workspace:{body.target_workspace_id}",
            details={"target_workspace_id": str(body.target_workspace_id)},
        )
    )
    await db.commit()

    token = create_access_token(
        user_id=current_user.user_id,
        email=current_user.email,
        workspace_id=body.target_workspace_id,
        role=current_user.role,
    )
    return TokenResponse(
        access_token=token,
        workspace_id=body.target_workspace_id,
        email=current_user.email,
    )
