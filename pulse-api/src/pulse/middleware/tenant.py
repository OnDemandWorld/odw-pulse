"""Tenant isolation middleware.

The workspace of a request is derived **exclusively from the verified JWT**
(``get_current_user`` → ``UserInToken.workspace_id``).  Earlier revisions of
this middleware also accepted an ``X-Workspace-Id`` header and a
``workspace_id`` query parameter, but client-supplied workspace identifiers
are untrusted input and were never consumed downstream — they are gone now.

This middleware remains the single place that marks public endpoints
(health checks, ``/docs``, login, …) and initialises
``request.state.workspace_id``.  It intentionally never *chooses* a
workspace on its own; that is an authentication-layer concern.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Paths that do not require workspace context.
_PUBLIC_PATHS: tuple[str, ...] = (
    "/health",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that annotates requests with workspace context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ``request.state.workspace_id`` starts unset for every request and
        # is populated only from the authenticated user (see
        # ``pulse.auth.dependencies.get_current_user``).  Keeping the
        # attribute present-but-None on public paths preserves the
        # previous request-state contract for any middleware added later.
        request.state.workspace_id = None
        if self._is_public(request.url.path):
            return await call_next(request)
        return await call_next(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_public(path: str) -> bool:
        """Return *True* when *path* does not require workspace context."""
        return any(path == p or path.startswith(p + "/") for p in _PUBLIC_PATHS)


__all__ = ["TenantMiddleware"]
