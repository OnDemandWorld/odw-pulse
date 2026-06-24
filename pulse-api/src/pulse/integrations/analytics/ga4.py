"""Google Analytics 4 (GA4) Measurement Protocol connector."""

from __future__ import annotations

from typing import Any

import httpx

from pulse.config import get_settings
from pulse.integrations.analytics.base import AnalyticsConnector


class GA4Connector(AnalyticsConnector):
    """Send analytics events via the GA4 Measurement Protocol.

    Required settings:
    * ``ga4_measurement_id`` — e.g. ``G-XXXXXXXXXX``
    * ``ga4_api_secret``     — data-stream API secret
    """

    def __init__(
        self,
        measurement_id: str | None = None,
        api_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._measurement_id = measurement_id or settings.ga4_measurement_id or ""
        self._api_secret = api_secret or settings.ga4_api_secret or ""
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=10.0)

    @property
    def _collect_url(self) -> str:
        return (
            f"https://www.google-analytics.com/mp/collect"
            f"?measurement_id={self._measurement_id}&api_secret={self._api_secret}"
        )

    # ------------------------------------------------------------------
    # AnalyticsConnector interface
    # ------------------------------------------------------------------

    def normalize(self, event: dict[str, Any]) -> dict[str, Any]:
        """Map a Pulse event to a GA4 Measurement Protocol payload."""
        params: dict[str, Any] = {"source": "pulse"}
        params.update(event.get("properties", {}))

        return {
            "client_id": str(event.get("user_id", "anonymous")),
            "events": [
                {
                    "name": event.get("event_name", "pulse_event"),
                    "params": params,
                }
            ],
        }

    async def send(self, event: dict[str, Any]) -> None:
        if not self._measurement_id or not self._api_secret:
            return  # silently skip when not configured
        payload = self.normalize(event)
        await self._http.post(self._collect_url, json=payload)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()
