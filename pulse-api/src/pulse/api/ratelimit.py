"""Fixed-window, per-client rate limiting for unauthenticated endpoints.

Exposes ready-made dependencies for the expensive/attackable anonymous
surface (BUILD_REPORT C-3): ``login_rate_limit`` and
``register_rate_limit``.  Each allows a configurable number of attempts
per client IP per 60-second window and raises ``429`` with a
``Retry-After`` header beyond that.

Counters live in the shared :class:`~pulse.core.redis_kv.RedisKV` store,
so all API replicas share one budget when Redis is up and fall back to
per-process counters when it is not (fail-soft, like job dispatch).

Client identity (audit finding #52): ``X-Forwarded-For`` is honored only
when the socket peer is a configured trusted proxy
(``RATE_LIMIT_TRUSTED_PROXIES`` CIDRs).  The rightmost *untrusted* XFF
entry is then the real client — a client-supplied spoofed leftmost entry
can no longer mint fresh rate-limit counters.  Direct (non-proxy)
connections always use the socket peer.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from pulse.config import get_settings
from pulse.core.redis_kv import get_kv_store

WINDOW_SECONDS = 60


@lru_cache(maxsize=8)
def _trusted_networks(cidrs: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    nets = []
    for entry in cidrs.split(","):
        entry = entry.strip()
        if entry:
            nets.append(ipaddress.ip_network(entry, strict=False))
    return tuple(nets)


def _is_trusted(ip: str, networks: tuple[Any, ...]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def client_ip(request: Request) -> str:
    """Client identity: rightmost untrusted XFF entry behind a trusted proxy."""
    peer = request.client.host if request.client else "unknown"
    networks = _trusted_networks(get_settings().rate_limit_trusted_proxies)
    if not _is_trusted(peer, networks):
        # Direct connection (or untrusted proxy): the header is spoofable.
        return peer
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        for entry in reversed(forwarded.split(",")):
            entry = entry.strip()
            if entry and not _is_trusted(entry, networks):
                return entry
    return peer


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
