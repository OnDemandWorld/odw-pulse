"""Best-effort dispatch of bulk jobs onto the Redis Streams queue."""

from __future__ import annotations

import logging

from pulse.worker.redis_client import RedisClient

logger = logging.getLogger(__name__)


async def enqueue_job(job_id: str, redis_url: str | None = None) -> bool:
    """Append *job_id* to the bulk-job stream.

    Returns ``True`` on success.  Returns ``False`` (instead of raising) when
    Redis is unreachable so callers can fall back to in-process execution —
    useful for minimal dev setups without the full stack.
    """
    client = RedisClient(redis_url)
    try:
        await client.connect()
        try:
            await client.ensure_group()
            await client.push_job(job_id)
        finally:
            await client.disconnect()
        return True
    except Exception:
        logger.warning(
            "Redis unavailable; bulk job %s was not enqueued", job_id, exc_info=True
        )
        return False


__all__ = ["enqueue_job"]
