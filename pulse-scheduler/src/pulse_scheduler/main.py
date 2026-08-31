"""Pulse scheduler entry point."""

import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

logger = structlog.get_logger()

# How often to sweep for orphaned bulk jobs.
_REAP_INTERVAL_SECONDS = 300
_HEARTBEAT_INTERVAL_SECONDS = 60


async def tick() -> None:
    """Placeholder scheduled task (proof-of-life log line)."""
    logger.info("pulse-scheduler.tick")


async def reap_stale_bulk_jobs() -> None:
    """Fail abandoned RUNNING bulk jobs and requeue abandoned PENDING ones."""
    try:
        from pulse.worker.maintenance import reap_stale_jobs

        stats = await reap_stale_jobs()
        logger.info("pulse-scheduler.reap", **stats)
    except Exception as exc:  # keep the scheduler alive regardless
        logger.error("pulse-scheduler.reap_error", error=str(exc))


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        job_defaults={
            # Never run two instances of the same job concurrently and fold
            # missed fires (e.g. after a pause) into a single run.
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60,
        }
    )
    scheduler.add_job(tick, "interval", seconds=_HEARTBEAT_INTERVAL_SECONDS, id="heartbeat")
    scheduler.add_job(
        reap_stale_bulk_jobs,
        "interval",
        seconds=_REAP_INTERVAL_SECONDS,
        id="bulk-job-reaper",
    )
    # TODO: register further scheduled jobs here
    return scheduler


async def main() -> None:
    logger.info("pulse-scheduler.started")
    scheduler = build_scheduler()
    scheduler.start()

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    try:
        await shutdown_event.wait()
    finally:
        # wait=False so shutdown does not block past the container's SIGTERM
        # grace period (docker then SIGKILLs); running jobs get that grace
        # period to finish.
        scheduler.shutdown(wait=False)
        logger.info("pulse-scheduler.stopped")


if __name__ == "__main__":  # pragma: no cover
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
