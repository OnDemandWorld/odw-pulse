"""Integration-skeleton tests (TSD §2.11, §2.12, §2.14)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

import httpx
import pytest

from pulse.integrations.analytics.segment import SegmentConnector
from pulse.integrations.storage.client import StorageClient
from pulse.integrations.vault.client import VaultClient
from pulse.integrations.webhooks.dispatcher import WebhookDispatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockTransport(httpx.MockTransport):
    """httpx.MockTransport subclass that records requests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._responses: list[httpx.Response] = []

    def queue(self, response: httpx.Response) -> None:
        self._responses.append(response)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._responses:
            resp = self._responses.pop(0)
            resp.request = request
            return resp
        return httpx.Response(status_code=200, json={"ok": True})


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vault_client_search_returns_results() -> None:
    """VaultClient.search() returns a list of mock results."""
    transport = _MockTransport()
    transport.queue(httpx.Response(200, json=[]))

    async with VaultClient(
        api_url="https://vault.test",
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    ) as client:
        results = await client.search("brand", workspace_id=uuid.uuid4())

    assert isinstance(results, list)
    # The mock implementation always returns at least one item.
    assert len(results) >= 1
    assert results[0]["title"]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_client_upload_and_download() -> None:
    """StorageClient.upload_file stores bytes; download_file retrieves them."""
    transport = _MockTransport()
    transport.queue(httpx.Response(200, headers={"ETag": '"abc123"'}))
    transport.queue(httpx.Response(200, content=b"hello-storage"))

    async with StorageClient(
        endpoint="https://minio.test",
        access_key="AK",
        secret_key="SK",
        bucket="pulse-test",
        http_client=httpx.AsyncClient(transport=transport),
    ) as client:
        info = await client.upload_file("folder/obj.bin", b"hello-storage")
        data = await client.download_file("folder/obj.bin")

    assert info["key"] == "folder/obj.bin"
    assert info["bucket"] == "pulse-test"
    assert data == b"hello-storage"


# ---------------------------------------------------------------------------
# Webhook dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_dispatcher_signs_payload() -> None:
    """WebhookDispatcher.dispatch() sends a signed POST request."""
    transport = _MockTransport()
    transport.queue(httpx.Response(200, json={"received": True}))

    dispatcher = WebhookDispatcher(http_client=httpx.AsyncClient(transport=transport))

    class _Config:
        url = "https://subscriber.test/hook"
        signing_secret = "super-secret"

    payload = {"content_id": "abc-123", "action": "approved"}
    await dispatcher.dispatch("content.approved", payload, _Config())

    assert len(transport.requests) == 1
    req = transport.requests[0]

    # Verify signature header is present and matches the body.
    sig_header = req.headers.get("X-Pulse-Signature", "")
    assert sig_header.startswith("sha256=")

    body = req.content
    expected = "sha256=" + hmac.new(
        b"super-secret", body, hashlib.sha256
    ).hexdigest()
    assert sig_header == expected

    # Verify JSON body structure.
    parsed = json.loads(body)
    assert parsed["event"] == "content.approved"
    assert parsed["data"] == payload


# ---------------------------------------------------------------------------
# Segment connector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_segment_connector_sends_event() -> None:
    """SegmentConnector.send() POSTs a normalised payload to Segment."""
    transport = _MockTransport()
    transport.queue(httpx.Response(200, json={"success": True}))

    connector = SegmentConnector(
        write_key="test_write_key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    event: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "event_name": "content.generated",
        "properties": {"market": "de-DE", "word_count": 120},
    }
    await connector.send(event)

    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert req.url.host == "api.segment.io"

    body = json.loads(req.content)
    assert body["event"] == "content.generated"
    assert body["properties"]["market"] == "de-DE"

    await connector.close()
