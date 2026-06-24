"""Abstract base for analytics connectors."""

from __future__ import annotations

import abc
from typing import Any


class AnalyticsConnector(abc.ABC):
    """Interface every analytics connector must implement.

    Subclasses adapt Pulse's internal event schema to the wire format
    required by the target analytics platform.
    """

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def send(self, event: dict[str, Any]) -> None:
        """Deliver a single analytics *event* to the remote platform."""

    @abc.abstractmethod
    def normalize(self, event: dict[str, Any]) -> dict[str, Any]:
        """Map a Pulse event dict to the platform-specific payload shape.

        This is a pure function (no I/O) so it can be unit-tested easily.
        """

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def send_batch(self, events: list[dict[str, Any]]) -> None:
        """Send every event in *events* sequentially.

        Subclasses may override this with a platform-native batch API.
        """
        for event in events:
            await self.send(event)

    async def close(self) -> None:  # noqa: B027
        """Release any underlying HTTP resources.

        Subclasses that allocate resources (HTTP clients, connection pools)
        should override this method.  The default implementation is a no-op.
        """

    async def __aenter__(self) -> AnalyticsConnector:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
