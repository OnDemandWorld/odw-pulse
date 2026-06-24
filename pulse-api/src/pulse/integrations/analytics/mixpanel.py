"""Mixpanel analytics connector."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from pulse.config import get_settings
from pulse.integrations.analytics.base import AnalyticsConnector


class MixpanelConnector(AnalyticsConnector):
    """Send analytics events to `Mixpanel <https://mixpanel.com>`_.

    Uses the Mixpanel HTTP import/track endpoint.  The project token is
    read from ``settings.mixpanel_project_token``.
    """

    TRACK_URL = "https://api.mixpanel.com/track"

    def __init__(
        self,
        project_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._project_token = project_token or settings.mixpanel_project_token or ""
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # AnalyticsConnector interface
    # ------------------------------------------------------------------

    def normalize(self, event: dict[str, Any]) -> dict[str, Any]:
        """Map a Pulse event to the Mixpanel track payload."""
        properties: dict[str, Any] = {
            "token": self._project_token,
            "source": "pulse",
        }
        properties.update(event.get("properties", {}))

        return {
            "event": event.get("event_name", "pulse_event"),
            "properties": {
                **properties,
                "distinct_id": str(event.get("user_id", "anonymous")),
            },
        }

    async def send(self, event: dict[str, Any]) -> None:
        if not self._project_token:
            return  # silently skip when not configured
        payload = self.normalize(event)
        # Mixpanel accepts JSON payloads via the data query parameter
        # (base64-encoded) or as a raw JSON body with the correct
        # content-type.  We use the JSON body approach.
        data_param = base64.b64encode(json.dumps(payload).encode()).decode()
        await self._http.post(
            self.TRACK_URL,
            params={"data": data_param},
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._owns_client:
            await self._http.aclose()
