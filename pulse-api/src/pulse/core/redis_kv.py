"""Best-effort TTL key/value store shared by rate limiting and revocation.

The auth hardening features need small amounts of short-lived state that
must be visible across API replicas:

* per-client request counters (``pulse.api.ratelimit``, BUILD_REPORT C-3)
* revoked-token markers (``pulse.auth.revocation``, BUILD_REPORT C-4)

Redis (``REDIS_URL``, already provisioned for the bulk-job stream) is the
preferred store.  Because these features guard the authentication path
itself, they must keep working when Redis is down — every operation
therefore degrades to an in-process TTL dictionary.  That weakens limits
and revocation to per-replica state until Redis recovers, which is the
intended trade-off: fail soft, never lock users out of a live login.

Once a Redis operation fails the store marks it unavailable for
:data:`REPROBE_SECONDS` so a dead Redis does not add connect attempts to
every request.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pulse.config import get_settings

logger = logging.getLogger(__name__)

# How long to avoid re-probing Redis after a failure.
REPROBE_SECONDS = 30.0

# Minimum gap between local-expired-key sweeps.
_PRUNE_INTERVAL_SECONDS = 60.0


class RedisKV:
    """TTL key/value store backed by Redis with an in-process fallback."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().redis_url
        self._redis: Any = None
        self._unavailable_until = 0.0
        self._last_prune = 0.0
        # Local fallback tables: key -> (monotonic expiry, payload)
        self._local_counts: dict[str, tuple[float, int]] = {}
        self._local_values: dict[str, tuple[float, str]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def _client(self) -> Any | None:
        """Return a live Redis client, or *None* while unavailable."""
        now = time.monotonic()
        if self._redis is not None:
            return self._redis
        if now < self._unavailable_until:
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            logger.info("KV store connected to Redis at %s", self._redis_url)
            return client
        except Exception as exc:  # pragma: no cover - depends on environment
            self._mark_unavailable(exc)
            return None

    def _mark_unavailable(self, exc: BaseException) -> None:
        """Drop the client and stop re-probing for a while."""
        self._redis = None
        self._unavailable_until = time.monotonic() + REPROBE_SECONDS
        logger.warning("Redis KV unavailable (%s); using in-process fallback", exc)

    def use_local_only(self, seconds: float = 3600.0) -> None:
        """Short-circuit Redis for *seconds*, pinning the in-process store.

        Used by the test suite so local state never leaks into a developer's
        running Redis (and test outcomes never depend on it).
        """
        self._redis = None
        self._unavailable_until = time.monotonic() + seconds

    def reset_local_state(self) -> None:
        """Clear all in-process counters and values (test isolation)."""
        self._local_counts.clear()
        self._local_values.clear()
        self._last_prune = 0.0

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def incr(self, key: str, ttl_seconds: int) -> tuple[int, int]:
        """Count *key* within a fixed window of *ttl_seconds* (reset on first hit).

        Returns ``(count, retry_after_seconds)``.
        """
        client = await self._client()
        if client is not None:
            try:
                count = int(await client.incr(key))
                if count == 1:
                    await client.expire(key, ttl_seconds)
                remaining = await client.ttl(key)
                retry_after = ttl_seconds if remaining is None or int(remaining) < 0 else int(remaining)
                return count, max(retry_after, 1)
            except Exception as exc:
                self._mark_unavailable(exc)
        return self._local_incr(key, ttl_seconds)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store *value* under *key*, expiring after *ttl_seconds*."""
        client = await self._client()
        if client is not None:
            try:
                await client.set(key, value, ex=max(ttl_seconds, 1))
                return
            except Exception as exc:
                self._mark_unavailable(exc)
        self._local_values[key] = (time.monotonic() + ttl_seconds, value)
        self._prune()

    async def get(self, key: str) -> str | None:
        """Return the value for *key*, or *None* when absent/expired."""
        client = await self._client()
        if client is not None:
            try:
                raw = await client.get(key)
                return None if raw is None else str(raw)
            except Exception as exc:
                self._mark_unavailable(exc)
        expires_at, value = self._local_values.get(key, (0.0, ""))
        if time.monotonic() >= expires_at:
            self._local_values.pop(key, None)
            return None
        return value

    # ------------------------------------------------------------------
    # In-process fallback internals
    # ------------------------------------------------------------------

    def _local_incr(self, key: str, ttl_seconds: int) -> tuple[int, int]:
        now = time.monotonic()
        expires_at, count = self._local_counts.get(key, (now + ttl_seconds, 0))
        if now >= expires_at:
            expires_at, count = now + ttl_seconds, 0
        count += 1
        self._local_counts[key] = (expires_at, count)
        self._prune()
        return count, max(int(expires_at - now), 1)

    def _prune(self) -> None:
        """Drop expired local keys, at most once per minute."""
        now = time.monotonic()
        if now - self._last_prune < _PRUNE_INTERVAL_SECONDS:
            return
        self._last_prune = now
        for table in (self._local_counts, self._local_values):
            for expired in [k for k, (exp, _) in table.items() if now >= exp]:
                del table[expired]


_store: RedisKV | None = None


def get_kv_store() -> RedisKV:
    """Return the process-wide KV store, creating it on first call."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = RedisKV()
    return _store
