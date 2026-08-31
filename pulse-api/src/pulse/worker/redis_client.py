"""Redis client for bulk-job stream queuing."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from pulse.config import get_settings

logger = logging.getLogger(__name__)

# Default Redis Streams key for bulk job dispatch.
BULK_JOB_STREAM = "pulse:bulk_jobs"

# Default consumer group shared by all bulk-job workers.
CONSUMER_GROUP = "bulk_workers"


class RedisClient:
    """Thin wrapper around ``redis.asyncio`` for job-stream operations."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().redis_url
        self._redis: Any = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish the async Redis connection."""
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        logger.info("Connected to Redis at %s", self._redis_url)

    async def disconnect(self) -> None:
        """Close the async Redis connection (safe to call when broken)."""
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    async def push_job(self, job_id: str, stream: str = BULK_JOB_STREAM) -> None:
        """Append a job ID to a Redis Stream for worker consumption."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        await self._redis.xadd(stream, {"job_id": job_id})
        logger.info("Pushed job %s to stream %s", job_id, stream)

    async def ensure_group(
        self,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
    ) -> None:
        """Create the consumer group if it does not exist (idempotent)."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        with contextlib.suppress(Exception):
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)

    async def consume_jobs(
        self,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
        consumer: str = "worker-1",
        batch_size: int = 1,
        block_ms: int = 5000,
    ) -> list[tuple[str, dict[str, str]]]:
        """Read new jobs from a Redis Stream.

        Returns a list of ``(message_id, fields)`` tuples.  An empty list
        means no jobs are available within the blocking window.  The consumer
        group must already exist (see :meth:`ensure_group`).
        """
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")

        raw: list[Any] = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=batch_size,
            block=block_ms,
        )

        jobs: list[tuple[str, dict[str, str]]] = []
        for _stream_name, messages in raw:
            for msg_id, fields in messages:
                jobs.append((msg_id, fields))
        return jobs

    async def claim_stale(
        self,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
        consumer: str = "worker-1",
        min_idle_ms: int = 60_000,
        count: int = 10,
    ) -> list[tuple[str, dict[str, str]]]:
        """Claim pending messages idle for longer than *min_idle_ms*.

        Recovers work assigned to consumers that crashed without
        acknowledging.  Returns ``(message_id, fields)`` tuples.
        """
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        _next_start, claimed, _deleted = await self._redis.xautoclaim(
            name=stream,
            groupname=group,
            consumername=consumer,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )
        return [(msg_id, fields) for msg_id, fields in claimed]

    async def pending_delivery_counts(
        self,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
    ) -> dict[str, int]:
        """Return ``{message_id: times_delivered}`` for all pending messages."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        entries: list[Any] = await self._redis.xpending_range(
            name=stream,
            groupname=group,
            min="-",
            max="+",
            count=1000,
        )
        return {entry["message_id"]: int(entry["times_delivered"]) for entry in entries}

    async def ack(
        self,
        message_id: str,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
    ) -> None:
        """Acknowledge successful processing of a stream message."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        await self._redis.xack(stream, group, message_id)
