"""Pulse async worker entry point."""

import asyncio
import signal

import structlog

logger = structlog.get_logger()


class Worker:
    """Async worker that consumes tasks from Redis Streams."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        """Main worker loop."""
        logger.info("pulse-worker.started")
        # TODO: consume tasks from Redis Streams (XREADGROUP + XACK). The
        # in-process implementation lives in pulse-api/src/pulse/worker/ and
        # should move here so jobs run out-of-process.
        await self._shutdown_event.wait()
        logger.info("pulse-worker.stopped")

    def shutdown(self) -> None:
        self._shutdown_event.set()


def _handle_signals(worker: Worker) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.shutdown)


async def main() -> None:
    worker = Worker()
    _handle_signals(worker)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
