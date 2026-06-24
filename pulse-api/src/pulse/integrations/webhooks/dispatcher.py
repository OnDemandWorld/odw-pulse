"""WebhookDispatcher — signs and delivers outbound webhook events.

TSD §2.14 — when notable events occur (content approved, bulk job
completed, …) Pulse fires a webhook to every matching subscriber.  The
payload is HMAC-SHA256 signed with the subscriber's shared secret so the
receiver can verify authenticity.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx


class WebhookDispatcher:
    """Dispatch signed webhook payloads to subscriber endpoints.

    Parameters
    ----------
    http_client:
        Optional ``httpx.AsyncClient`` — inject a mock transport in tests.
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client if we created it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> WebhookDispatcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    @staticmethod
    def sign_payload(payload: bytes, secret: str) -> str:
        """Return the ``sha256=<hex>`` signature for *payload*."""
        digest = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
        webhook_config: Any,
    ) -> httpx.Response:
        """Deliver a signed webhook event to a single subscriber.

        Parameters
        ----------
        event_type:
            Machine-readable event name (e.g. ``content.approved``).
        payload:
            JSON-serialisable event body.
        webhook_config:
            An object exposing ``url: str`` and ``signing_secret: str``
            attributes.  The :class:`WebhookConfig` SQLAlchemy model
            satisfies this interface.

        Returns
        -------
        httpx.Response
            The HTTP response from the subscriber endpoint.
        """
        url: str = webhook_config.url
        secret: str = webhook_config.signing_secret

        body: dict[str, Any] = {
            "event": event_type,
            "timestamp": int(time.time()),
            "data": payload,
        }
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        signature = self.sign_payload(raw, secret)

        headers = {
            "Content-Type": "application/json",
            "X-Pulse-Event": event_type,
            "X-Pulse-Signature": signature,
            "X-Pulse-Timestamp": str(body["timestamp"]),
        }

        response = await self._http.post(url, content=raw, headers=headers)
        response.raise_for_status()
        return response
