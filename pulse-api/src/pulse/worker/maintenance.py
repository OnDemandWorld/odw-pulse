"""Recovery for bulk jobs orphaned by crashed workers or missed dispatch.

Two failure modes are handled:

* ``RUNNING`` jobs whose worker died mid-processing (no progress updates for
  longer than the staleness window) are marked ``FAILED``.  Live jobs keep
  bumping ``updated_at`` on every progress write, so only truly dead ones
  trip the window.
* ``PENDING`` jobs that were never picked up (Redis was down at dispatch
  time, the worker never started, …) are re-enqueued on the stream.

Run at worker startup and periodically by the scheduler.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from pulse.models.bulk_job import BulkJob, BulkJobStatus

logger = logging.getLogger(__name__)

# A job with no updates for this long is considered abandoned.
STALE_AFTER = timedelta(minutes=10)


async def reap_stale_jobs(
    session_factory: Any | None = None,
    stale_after: timedelta = STALE_AFTER,
) -> dict[str, int]:
    """Fail abandoned RUNNING jobs and requeue abandoned PENDING jobs.

    Args:
        session_factory: Optional ``async_sessionmaker`` (tests). Defaults to
            the application session factory.
        stale_after: How long a job may go without updates before it is
            considered abandoned.

    Returns:
        ``{"failed": n, "requeued": m}`` counters.
    """
    if session_factory is None:
        from pulse.db.session import get_session_factory

        session_factory = get_session_factory()

    cutoff = datetime.now(UTC) - stale_after
    stats = {"failed": 0, "requeued": 0}
    requeue_ids: list[str] = []

    async with session_factory() as db:
        # Jobs whose worker died mid-processing.
        result = await db.execute(
            select(BulkJob).where(
                BulkJob.status == BulkJobStatus.RUNNING,
                BulkJob.updated_at < cutoff,
            )
        )
        for job in result.scalars():
            job.status = BulkJobStatus.FAILED
            errors = dict(job.errors or {})
            errors["_worker"] = "Job reaped: worker stopped responding"
            job.errors = errors
            job.updated_at = datetime.now(UTC)
            stats["failed"] += 1

        # Jobs no consumer ever picked up.  Bump updated_at so the next
        # sweep does not requeue them again before a consumer catches up.
        result = await db.execute(
            select(BulkJob).where(
                BulkJob.status == BulkJobStatus.PENDING,
                BulkJob.updated_at < cutoff,
            )
        )
        for job in result.scalars():
            job.updated_at = datetime.now(UTC)
            requeue_ids.append(str(job.id))

        await db.commit()

    if requeue_ids:
        from pulse.worker.dispatch import enqueue_job

        for job_id in requeue_ids:
            if await enqueue_job(job_id):
                stats["requeued"] += 1
            else:
                # Redis is down — stop hammering it; the next sweep retries.
                logger.warning(
                    "Could not requeue stale bulk job %s (Redis unavailable)", job_id
                )
                break

    return stats


__all__ = ["STALE_AFTER", "reap_stale_jobs"]
