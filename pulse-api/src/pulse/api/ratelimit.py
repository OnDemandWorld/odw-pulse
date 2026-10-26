"""Fixed-window, per-client rate limiting for unauthenticated endpoints.

Exposes ready-made dependencies for the expensive/attackable anonymous
surface (BUILD_REPORT C-3): ``login_rate_limit`` and
``register_rate_limit``.  Each allows a configurable number of attempts
per client IP per 60-second window and raises ``429`` with a
``Retry-After`` header beyond that.

Counters live in the shared :class:`~pulse.core.redis_kv.RedisKV` store,
so all API replicas share one budget when Redis is up and fall back to
per-process counters when it is not (fail-soft, like job dispatch).

Client identity prefers the leftmost ``X-Forwarded-For`` entry — API
replicas sit behind the nginx ingress / compose proxy, so the socket peer
is the proxy, not the client.  This trusts the proxy to have appended the
real client address; deployments must not expose the API directly to
clients that can spoof the header.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from pulse.config import get_settings
from pulse.core.redis_kv import get_kv_store

WINDOW_SECONDS = 60


def client_ip(request: Request) -> str:
    """Best-effort client identity: leftmost XFF entry, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limiter(
    scope: str,
    limit_attr: str,
    window_seconds: int = WINDOW_SECONDS,
) -> Callable[..., Awaitable[None]]:
    """Build a dependency capping *scope* at ``settings.<limit_attr>`` hits/window.

    The limit is read from :class:`~pulse.config.Settings` at request time,
    so it is tunable via environment (and monkeypatchable in tests).  A
    limit of ``0`` (or ``rate_limit_enabled = false``) disables enforcement.
    """

    async def _enforce(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = int(getattr(settings, limit_attr))
        if limit <= 0:
            return
        key = f"pulse:ratelimit:{scope}:{client_ip(request)}"
        count, retry_after = await get_kv_store().incr(key, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests; please slow down and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return _enforce


#: Dependency for ``POST /auth/login`` — brute-force throttle.
login_rate_limit = rate_limiter("login", "rate_limit_login_per_minute")

#: Dependency for ``POST /auth/register`` — workspace-farming throttle.
register_rate_limit = rate_limiter("register", "rate_limit_register_per_minute")

# Type aliases for endpoint signatures.
LoginRateLimit = Annotated[Any, Depends(login_rate_limit)]
RegisterRateLimit = Annotated[Any, Depends(register_rate_limit)]
