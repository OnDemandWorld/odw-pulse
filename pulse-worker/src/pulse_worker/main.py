"""Pulse async worker — consumes bulk jobs from Redis Streams.

The worker reads job IDs from the ``pulse:bulk_jobs`` stream as part of the
``bulk_workers`` consumer group, processes them through the generation
pipeline, and acknowledges them.  Messages that fail are left pending and
recovered via ``XAUTOCLAIM``; after too many delivery attempts a job is
dead-lettered (marked FAILED in the database) and its message acknowledged.

At startup the worker also reaps jobs orphaned by previous crashes (see
``pulse.worker.maintenance.reap_stale_jobs``).

Set ``PULSE_METRICS_PORT`` to expose Prometheus counters on that port.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket

import structlog
from prometheus_client import Counter, start_http_server

from pulse.worker.redis_client import BULK_JOB_STREAM, CONSUMER_GROUP, RedisClient

logger = structlog.get_logger()

JOBS_TOTAL = Counter(
    "pulse_worker_jobs_total",
    "Bulk-job stream messages handled by this worker",
    ["result"],
)

DEFAULT_BATCH_SIZE = 1
DEFAULT_BLOCK_MS = 5_000
DEFAULT_MIN_IDLE_MS = 60_000  # claim pending messages idle for >1 minute
DEFAULT_MAX_ATTEMPTS = 5
# Recover stuck pending messages roughly every 30s (6 blocked reads of 5s).
_CLAIM_EVERY_CYCLES = 6


# ---------------------------------------------------------------------------
# Monkeypatchable hooks (also the seam used by the test-suite)
# ---------------------------------------------------------------------------


async def process_job(job_id: str) -> None:
    """Run one bulk job through the generation pipeline."""
    from pulse.worker.tasks import process_bulk_job

    await process_bulk_job(job_id)


async def mark_job_failed(job_id: str, reason: str) -> None:
    """Dead-letter hook: mark a job FAILED in the database."""
    import uuid as _uuid

    from pulse.db.session import get_session_factory
    from pulse.models.bulk_job import BulkJobStatus
    from pulse.services.bulk_job_service import BulkJobService

    svc = BulkJobService()
    factory = get_session_factory()
    async with factory() as db:
        job = await svc.get_job_unscoped(db, _uuid.UUID(job_id))
        if job.status in (BulkJobStatus.PENDING, BulkJobStatus.RUNNING):
            job.status = BulkJobStatus.FAILED
            errors = dict(job.errors or {})
            errors["_worker"] = reason
            job.errors = errors
            await db.commit()


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class Worker:
    """Redis Streams consumer for bulk generation jobs."""

    def __init__(
        self,
        redis_url: str | None = None,
        consumer_name: str | None = None,
        *,
        stream: str = BULK_JOB_STREAM,
        group: str = CONSUMER_GROUP,
        batch_size: int = DEFAULT_BATCH_SIZE,
        block_ms: int = DEFAULT_BLOCK_MS,
        min_idle_ms: int = DEFAULT_MIN_IDLE_MS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._client = RedisClient(redis_url)
        self._consumer_name = consumer_name or f"{socket.gethostname()}-{os.getpid()}"
        self._stream = stream
        self._group = group
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._min_idle_ms = min_idle_ms
        self._max_attempts = max_attempts
        self._shutdown_event = asyncio.Event()
        self._cycles = 0

    def shutdown(self) -> None:
        self._shutdown_event.set()

    async def run(self) -> None:
        """Main worker loop.

        Survives Redis outages (at startup and mid-run) by reconnecting with
        backoff until shut down.
        """
        logger.info("pulse-worker.started", consumer=self._consumer_name)
        retry_seconds = 5.0
        while not self._shutdown_event.is_set():
            try:
                await self._client.connect()
                await self._client.ensure_group(self._stream, self._group)
                await self._startup_reap()
                await self._consume_loop()
                break  # _consume_loop only returns on shutdown
            except Exception as exc:  # noqa: BLE001 - reconnect on any failure
                logger.warning(
                    "pulse-worker.redis_unavailable",
                    error=str(exc),
                    retry_in_seconds=retry_seconds,
                )
                try:
                    await self._client.disconnect()
                except Exception:  # pragma: no cover - defensive
                    pass
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=retry_seconds
                    )
                except TimeoutError:
                    continue
        logger.info("pulse-worker.stopped")

    async def _startup_reap(self) -> None:
        """Recover jobs orphaned by a previous crash (non-fatal if it fails)."""
        from pulse.worker.maintenance import reap_stale_jobs

        try:
            stats = await reap_stale_jobs()
            logger.info("pulse-worker.startup_reap", **stats)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("pulse-worker.startup_reap_error", error=str(exc))

    async def _consume_loop(self) -> None:
        """Read and process messages until shutdown is requested."""
        while not self._shutdown_event.is_set():
            messages = await self._client.consume_jobs(
                stream=self._stream,
                group=self._group,
                consumer=self._consumer_name,
                batch_size=self._batch_size,
                block_ms=self._block_ms,
            )
            for message_id, fields in messages:
                await self.handle_message(message_id, fields, attempts=1)

            self._cycles += 1
            if self._cycles % _CLAIM_EVERY_CYCLES == 0:
                await self._recover_pending()

    async def _recover_pending(self) -> None:
        """Claim messages stuck with dead consumers; retry or dead-letter them."""
        try:
            counts = await self._client.pending_delivery_counts(
                stream=self._stream, group=self._group
            )
            claimed = await self._client.claim_stale(
                stream=self._stream,
                group=self._group,
                consumer=self._consumer_name,
                min_idle_ms=self._min_idle_ms,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("pulse-worker.claim_error", error=str(exc))
            return

        for message_id, fields in claimed:
            await self.handle_message(
                message_id, fields, attempts=counts.get(message_id, 1)
            )

    async def handle_message(
        self, message_id: str, fields: dict[str, str], attempts: int
    ) -> bool:
        """Process one stream message.

        Returns ``True`` when the message was acknowledged (done or
        dead-lettered), ``False`` when it stays pending for a later retry.
        """
        job_id = fields.get("job_id") if fields else None
        if not job_id:
            logger.warning("pulse-worker.poison_message", message_id=message_id)
            await self._client.ack(message_id, stream=self._stream, group=self._group)
            JOBS_TOTAL.labels(result="skipped").inc()
            return True

        if attempts > self._max_attempts:
            logger.error(
                "pulse-worker.dead_letter", job_id=job_id, attempts=attempts
            )
            try:
                await mark_job_failed(
                    job_id, f"Abandoned after {attempts} delivery attempts"
                )
            except Exception:  # pragma: no cover - defensive
                logger.exception("pulse-worker.dead_letter_db_error", job_id=job_id)
            await self._client.ack(message_id, stream=self._stream, group=self._group)
            JOBS_TOTAL.labels(result="dead_letter").inc()
            return True

        try:
            await process_job(job_id)
        except Exception as exc:
            logger.error(
                "pulse-worker.job_error",
                job_id=job_id,
                attempts=attempts,
                error=str(exc),
            )
            JOBS_TOTAL.labels(result="failed").inc()
            return False  # leave pending; recovered via _recover_pending

        await self._client.ack(message_id, stream=self._stream, group=self._group)
        JOBS_TOTAL.labels(result="succeeded").inc()
        logger.info("pulse-worker.job_done", job_id=job_id, attempts=attempts)
        return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _handle_signals(worker: Worker) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.shutdown)


def _maybe_start_metrics_server() -> None:
    port = os.environ.get("PULSE_METRICS_PORT")
    if port:
        start_http_server(int(port))
        logger.info("pulse-worker.metrics_server", port=int(port))


async def main() -> None:
    _maybe_start_metrics_server()
    worker = Worker()
    _handle_signals(worker)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
