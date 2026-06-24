"""Pulse async worker entry point."""

import asyncio
import signal
from typing import Any

import structlog

logger = structlog.get_logger()


class Worker:
    """Async worker that consumes tasks from Redis Streams."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Main worker loop."""
        logger.info("pulse-worker.started")
        while not self._shutdown_event.is_set():
            try:
                # TODO: consume tasks from Redis Streams
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("pulse-worker.loop_error", exc=str(exc))
                await asyncio.sleep(1)
        logger.info("pulse-worker.stopped")

    def shutdown(self) -> None:
        self._shutdown_event.set()


def _handle_signals(worker: Worker) -> None:
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.shutdown)


async def main() -> None:
    worker = Worker()
    _handle_signals(worker)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
