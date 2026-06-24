"""Redis client for bulk-job stream queuing."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from pulse.config import get_settings

logger = logging.getLogger(__name__)

# Default Redis Streams key for bulk job dispatch.
BULK_JOB_STREAM = "pulse:bulk_jobs"


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
        """Close the async Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    async def push_job(self, job_id: str, stream: str = BULK_JOB_STREAM) -> None:
        """Append a job ID to a Redis Stream for worker consumption."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        await self._redis.xadd(stream, {"job_id": job_id})
        logger.info("Pushed job %s to stream %s", job_id, stream)

    async def consume_jobs(
        self,
        stream: str = BULK_JOB_STREAM,
        group: str = "bulk_workers",
        consumer: str = "worker-1",
        batch_size: int = 1,
        block_ms: int = 5000,
    ) -> list[tuple[str, dict[str, str]]]:
        """Read pending jobs from a Redis Stream.

        Returns a list of ``(message_id, fields)`` tuples.  An empty list
        means no jobs are available within the blocking window.
        """
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")

        # Create the consumer group (idempotent).
        with contextlib.suppress(Exception):
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)

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

    async def ack(
        self,
        message_id: str,
        stream: str = BULK_JOB_STREAM,
        group: str = "bulk_workers",
    ) -> None:
        """Acknowledge successful processing of a stream message."""
        if self._redis is None:
            raise RuntimeError("Redis client not connected; call connect() first")
        await self._redis.xack(stream, group, message_id)
