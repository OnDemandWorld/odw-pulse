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
from pulse.integrations.webhooks.url_guard import WebhookURLBlockedError, validate_webhook_url

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


# ---------------------------------------------------------------------------
# Webhook URL SSRF guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://127.0.0.1:8000/admin",  # loopback
        "http://10.0.0.5/internal",  # private range
        "http://192.168.1.1/",  # private range
        "http://[::1]/x",  # IPv6 loopback
        "ftp://93.184.216.34/file",  # disallowed scheme
        "file:///etc/passwd",  # disallowed scheme
        "not a url at all",  # no scheme/host
    ],
)
def test_webhook_url_guard_blocks_dangerous_targets(url: str) -> None:
    """Private/loopback/link-local addresses and non-http(s) schemes are rejected."""
    with pytest.raises(WebhookURLBlockedError):
        validate_webhook_url(url)


def test_webhook_url_guard_allows_public_https() -> None:
    """A public HTTPS endpoint passes validation (no DNS needed for literals)."""
    validate_webhook_url("https://93.184.216.34/hook")  # example.com address


def test_webhook_url_guard_blocks_hostnames_resolving_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hostnames that resolve to blocked ranges are rejected too."""
    import socket

    import pulse.integrations.webhooks.url_guard as url_guard

    def _fake_getaddrinfo(host: str, *args: object, **kwargs: object) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.1.2.3", 0))]

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", _fake_getaddrinfo)
    with pytest.raises(WebhookURLBlockedError, match="blocked address"):
        validate_webhook_url("https://internal.corp/hook")


def test_webhook_url_guard_production_requires_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In production only the https scheme is accepted."""
    import pulse.integrations.webhooks.url_guard as url_guard

    class _ProdSettings:
        is_production = True

    monkeypatch.setattr(url_guard, "get_settings", lambda: _ProdSettings())
    with pytest.raises(WebhookURLBlockedError, match="not allowed"):
        validate_webhook_url("http://93.184.216.34/hook")
    validate_webhook_url("https://93.184.216.34/hook")


@pytest.mark.asyncio
async def test_register_webhook_with_private_url_returns_400(
    authorized_client: Any,
) -> None:
    """The API rejects webhook registrations pointing at internal addresses."""
    response = await authorized_client.post(
        "/api/v1/webhooks",
        json={
            "url": "http://169.254.169.254/latest/meta-data/",
            "signing_secret": "test-secret-123",
            "events": [],
        },
    )
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_webhook_with_public_url_succeeds(
    authorized_client: Any,
) -> None:
    """A public webhook URL registers successfully."""
    response = await authorized_client.post(
        "/api/v1/webhooks",
        json={
            "url": "https://93.184.216.34/hook",
            "signing_secret": "test-secret-123",
            "events": ["content.approved"],
        },
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://93.184.216.34/hook"
