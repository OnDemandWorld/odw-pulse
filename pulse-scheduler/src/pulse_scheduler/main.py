"""Pulse scheduler entry point."""

import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

logger = structlog.get_logger()


async def tick() -> None:
    """Placeholder scheduled task."""
    logger.info("pulse-scheduler.tick")


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
    # TODO: register real scheduled jobs here
    scheduler.add_job(tick, "interval", seconds=60, id="heartbeat")
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
