"""Best-effort dispatch of bulk jobs onto the Redis Streams queue."""

from __future__ import annotations

import contextlib
import logging

from pulse.worker.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Reused across enqueues (audit finding #91): a fresh connection + group
# round-trip per job made reaper sweeps of N jobs pay N handshakes.
_shared_client: RedisClient | None = None
_group_ready = False


async def enqueue_job(job_id: str, redis_url: str | None = None) -> bool:
    """Append *job_id* to the bulk-job stream.

    Returns ``True`` on success.  Returns ``False`` (instead of raising) when
    Redis is unreachable so callers can fall back to in-process execution —
    useful for minimal dev setups without the full stack.
    """
    global _shared_client, _group_ready  # noqa: PLW0603
    try:
        if _shared_client is None:
            _shared_client = RedisClient(redis_url)
            await _shared_client.connect()
            _group_ready = False
        if not _group_ready:
            await _shared_client.ensure_group()
            _group_ready = True
        await _shared_client.push_job(job_id)
        return True
    except Exception:
        # Drop the broken client so the next call reconnects cleanly.
        if _shared_client is not None:
            with contextlib.suppress(Exception):
                await _shared_client.disconnect()
        _shared_client = None
        _group_ready = False
        logger.warning(
            "Redis unavailable; bulk job %s was not enqueued", job_id, exc_info=True
        )
        return False


__all__ = ["enqueue_job"]
