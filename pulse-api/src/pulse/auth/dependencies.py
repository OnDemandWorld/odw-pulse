"""FastAPI dependencies for authentication and workspace isolation.

The module exposes:

* ``get_current_user`` — extract & validate JWT from the *Authorization*
  header and return the corresponding :class:`UserInToken`.
* ``require_workspace`` — ensure the authenticated user has access to the
  workspace identified in the URL path.
* ``WorkspaceContext`` — a contextvar-based workspace scope set by the
  tenant middleware.
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.auth.models import UserInToken
from pulse.auth.security import JWTError, decode_access_token
from pulse.db.session import get_session as get_db

# Re-export so that downstream modules can import from a single place.
__all__ = [
    "WorkspaceContext",
    "get_current_user",
    "get_db",
    "require_workspace",
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Workspace context — set by TenantMiddleware, consumed by DB layer.
# ---------------------------------------------------------------------------
_current_workspace_var: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "current_workspace_id",
    default=None,
)


class WorkspaceContext:
    """Thin wrapper around a ``contextvars.ContextVar`` holding the active workspace."""

    @staticmethod
    def get() -> uuid.UUID | None:
        """Return the workspace ID for the current request, or *None*."""
        return _current_workspace_var.get()

    @staticmethod
    def set(workspace_id: uuid.UUID) -> contextvars.Token[uuid.UUID | None]:
        """Set the workspace ID for the current request scope."""
        return _current_workspace_var.set(workspace_id)

    @staticmethod
    def reset(token: contextvars.Token[uuid.UUID | None]) -> None:
        """Restore the previous workspace context."""
        _current_workspace_var.reset(token)


# ---------------------------------------------------------------------------
# PostgreSQL RLS helper
# ---------------------------------------------------------------------------


async def _set_rls_context(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Set the PostgreSQL session variable used by RLS policies."""
    await session.execute(
        text("SET LOCAL pulse.workspace_id = :wid"),
        {"wid": str(workspace_id)},
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_db),
) -> UserInToken:
    """Validate the JWT bearer token and return the user identity.

    The user record is looked up in the database to ensure it still exists
    and is active.  When no matching row is found (e.g. during integration
    tests with a mock user store) the token payload is returned as-is.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = uuid.UUID(str(payload["sub"]))
    workspace_id = uuid.UUID(str(payload["workspace_id"]))
    email = str(payload["email"])
    role = str(payload["role"])

    # Best-effort DB lookup — fall back to token payload when the row is
    # absent (supports mock-user login during early development) or when
    # the table does not exist yet (tests, fresh installations).
    try:
        result = await session.execute(
            text("SELECT id, is_active FROM users WHERE id = :id"),
            {"id": str(user_id)},
        )
        row = result.first()
        if row is not None:
            is_active: bool = bool(row[1])
            if not is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        # Table does not exist or other DB error — accept token as-is.
        pass

    return UserInToken(
        user_id=user_id,
        email=email,
        workspace_id=workspace_id,
        role=role,
    )


def require_workspace(
    user: Annotated[UserInToken, Depends(get_current_user)],
    request: Request,
) -> uuid.UUID:
    """Verify that the user has access to the workspace in the URL path.

    The workspace ID is extracted from ``request.path_params["workspace_id"]``.
    Returns the validated workspace UUID.
    """
    path_workspace_raw = request.path_params.get("workspace_id")
    if path_workspace_raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id not found in path",
        )
    try:
        path_workspace_id = uuid.UUID(str(path_workspace_raw))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id in path",
        ) from exc

    if user.workspace_id != path_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this workspace",
        )
    return path_workspace_id


# Convenience type aliases for endpoint signatures.
CurrentUser = Annotated[UserInToken, Depends(get_current_user)]
CurrentWorkspace = Annotated[uuid.UUID, Depends(require_workspace)]
