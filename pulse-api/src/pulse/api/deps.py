"""Re-export commonly used FastAPI dependencies.

Endpoint modules can import everything they need from this single module
instead of reaching into ``auth``, ``db.session``, etc.::

    from pulse.api.deps import CurrentUser, get_db
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from pulse.auth.dependencies import (
    CurrentUser,
    CurrentWorkspace,
    WorkspaceContext,
    get_current_user,
    require_workspace,
)
from pulse.auth.models import UserInToken
from pulse.db.session import get_session as get_db

__all__ = [
    "CurrentUser",
    "CurrentWorkspace",
    "WorkspaceContext",
    "get_current_user",
    "get_current_workspace",
    "get_db",
    "require_role",
    "require_workspace",
]


# ---------------------------------------------------------------------------
# Convenience: get_current_workspace
# ---------------------------------------------------------------------------


async def get_current_workspace(
    user: UserInToken = Depends(get_current_user),
) -> str:
    """Return the workspace ID (as string) from the authenticated user's token."""
    return str(user.workspace_id)


# ---------------------------------------------------------------------------
# Role-gating dependency factory
# ---------------------------------------------------------------------------


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """Return a dependency that ensures the user has one of *allowed_roles*."""

    async def _check_role(
        user: Annotated[UserInToken, Depends(get_current_user)],
    ) -> UserInToken:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted. Required: {allowed_roles}",
            )
        return user

    return _check_role
