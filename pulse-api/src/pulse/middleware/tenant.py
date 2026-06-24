"""Tenant isolation middleware.

:class:`TenantMiddleware` extracts the workspace identifier from the
incoming request (via the ``X-Workspace-Id`` header, ``X-API-Key`` header,
or ``workspace_id`` query parameter), validates it, and stores it in the
request state so that downstream code can set the PostgreSQL RLS context.

Public endpoints (health checks, ``/docs``, login, …) are whitelisted and
skip workspace resolution entirely.
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that do not require workspace context.
_PUBLIC_PATHS: tuple[str, ...] = (
    "/health",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class TenantMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that resolves the workspace for each request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ---- fast-path for public endpoints --------------------------------
        if self._is_public(request.url.path):
            request.state.workspace_id = None
            return await call_next(request)

        # ---- resolve workspace identifier ----------------------------------
        workspace_id: str | None = request.headers.get("X-Workspace-Id")

        if workspace_id is None:
            api_key: str | None = request.headers.get("X-API-Key")
            if api_key is not None:
                workspace_id = await self._workspace_from_api_key(api_key)

        if workspace_id is None:
            workspace_id = request.query_params.get("workspace_id")

        # No workspace context — allow the request through; downstream
        # dependencies (``get_current_user``) will enforce authentication.
        if workspace_id is None:
            request.state.workspace_id = None
            return await call_next(request)

        # ---- validate ------------------------------------------------------
        try:
            ws_uuid = self._parse_uuid(workspace_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Invalid workspace identifier: {workspace_id}"},
            )

        request.state.workspace_id = ws_uuid
        return await call_next(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_public(path: str) -> bool:
        """Return *True* when *path* does not require workspace context."""
        return any(path == p or path.startswith(p + "/") for p in _PUBLIC_PATHS)

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID:
        """Parse a UUID string, raising :class:`ValueError` on failure."""
        if not _UUID_RE.match(value):
            raise ValueError(value)
        return uuid.UUID(value)

    @staticmethod
    async def _workspace_from_api_key(api_key: str) -> str | None:
        """Look up the workspace associated with *api_key*.

        This is a stub — a real implementation would query the ``api_keys``
        table.  Returns *None* for now.
        """
        # TODO: query api_keys table
        _ = api_key  # suppress unused-argument lint
        return None


__all__ = ["TenantMiddleware"]
