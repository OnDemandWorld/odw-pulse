"""Segment analytics connector."""

from __future__ import annotations

from typing import Any

import httpx

from pulse.config import get_settings
from pulse.integrations.analytics.base import AnalyticsConnector


class SegmentConnector(AnalyticsConnector):
    """Send analytics events to `Segment <https://segment.com>`_.

    Uses the Segment HTTP Tracking API.  The write key is read from
    ``settings.segment_write_key``.
    """

    TRACK_URL = "https://api.segment.io/v1/track"

    def __init__(
        self,
        write_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._write_key = write_key or settings.segment_write_key or ""
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # AnalyticsConnector interface
    # ------------------------------------------------------------------

    def normalize(self, event: dict[str, Any]) -> dict[str, Any]:
        """Map a Pulse event to the Segment ``/v1/track`` shape."""
        return {
            "userId": str(event.get("user_id", "")),
            "event": event.get("event_name", "unknown"),
            "properties": event.get("properties", {}),
            "context": event.get("context", {}),
            "timestamp": event.get("timestamp"),
        }

    async def send(self, event: dict[str, Any]) -> None:
        payload = self.normalize(event)
        if not self._write_key:
            return  # silently skip when not configured
        await self._http.post(
            self.TRACK_URL,
            json=payload,
            auth=(self._write_key, ""),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()
