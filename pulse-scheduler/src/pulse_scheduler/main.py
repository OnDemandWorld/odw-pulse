"""Pulse scheduler entry point."""

import asyncio
import signal
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

logger = structlog.get_logger()


async def tick() -> None:
    """Placeholder scheduled task."""
    logger.info("pulse-scheduler.tick")


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    # TODO: register real scheduled jobs here
    scheduler.add_job(tick, "interval", seconds=60, id="heartbeat")
    return scheduler


async def main() -> None:
    logger.info("pulse-scheduler.started")
    scheduler = build_scheduler()
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        scheduler.shutdown()
        logger.info("pulse-scheduler.stopped")


if __name__ == "__main__":  # pragma: no cover
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
