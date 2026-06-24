"""StorageClient — S3-compatible object storage connector.

TSD §2.12 — binary assets (generated images, exported documents, …) are
persisted in an S3-compatible store (MinIO in self-hosted deployments,
AWS S3 in cloud).  This client uses ``httpx`` to speak the S3 REST API
directly so we do not force a heavy ``boto3`` dependency on every
environment.  A ``boto3``-backed variant can be dropped in later without
changing the call-sites.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
from typing import Any
from urllib.parse import quote

import httpx

from pulse.config import get_settings


class StorageClient:
    """Async S3-compatible object-storage client.

    Configuration is read from :class:`pulse.config.Settings`:

    * ``storage_endpoint`` — S3 endpoint URL (e.g. ``https://minio:9000``)
    * ``storage_access_key`` — AWS_ACCESS_KEY / MinIO access key
    * ``storage_secret_key`` — AWS_SECRET_KEY / MinIO secret key
    * ``storage_bucket``     — default bucket name
    * ``storage_region``     — AWS region (default ``us-east-1``)
    * ``storage_use_ssl``    — whether the endpoint uses HTTPS
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
        use_ssl: bool | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = (endpoint or settings.storage_endpoint or "http://localhost:9000").rstrip(
            "/"
        )
        self._access_key = access_key or settings.storage_access_key or ""
        self._secret_key = secret_key or settings.storage_secret_key or ""
        self._bucket = bucket or settings.storage_bucket
        self._region = region or settings.storage_region
        self._use_ssl = use_ssl if use_ssl is not None else settings.storage_use_ssl
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=60.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client if we created it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> StorageClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _object_url(self, key: str) -> str:
        """Return the full URL for an object key inside the bucket."""
        safe_key = quote(key, safe="/")
        return f"{self._endpoint}/{self._bucket}/{safe_key}"

    def _sign(
        self,
        method: str,
        key: str,
        content_type: str = "",
        expires: int = 3600,
    ) -> dict[str, str]:
        """Generate a minimal V2-style signature for presigned URLs.

        This is a simplified demonstration signature — production code
        should use full AWS SigV4.
        """
        now = dt.datetime.now(dt.UTC)
        date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        expiry = int(now.timestamp()) + expires
        string_to_sign = f"{method}\n\n{content_type}\n{expiry}\n/{self._bucket}/{key}"
        signature = base64.b64encode(
            hmac.new(
                self._secret_key.encode(),
                string_to_sign.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
        return {
            "AWSAccessKeyId": self._access_key,
            "Expires": str(expiry),
            "Signature": signature,
            "Date": date_str,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        key: str,
        data: bytes | str,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload *data* to *key* in the configured bucket.

        Returns a dict with the object URL and ETag (if available).
        """
        if isinstance(data, str):
            data = data.encode()

        url = self._object_url(key)
        headers = {"Content-Type": content_type}

        # In a real implementation we'd add Authorization headers here.
        # For now we just PUT the bytes.
        response = await self._http.put(url, content=data, headers=headers)
        response.raise_for_status()

        return {
            "key": key,
            "bucket": self._bucket,
            "url": url,
            "etag": response.headers.get("ETag", ""),
        }

    async def download_file(self, key: str) -> bytes:
        """Download the object at *key* and return its raw bytes."""
        url = self._object_url(key)
        response = await self._http.get(url)
        response.raise_for_status()
        return response.content

    async def get_presigned_url(
        self,
        key: str,
        expires: int = 3600,
    ) -> str:
        """Return a presigned URL that grants temporary GET access to *key*."""
        params = self._sign("GET", key, expires=expires)
        url = self._object_url(key)
        query = "&".join(f"{quote(k)}={quote(v)}" for k, v in params.items())
        return f"{url}?{query}"
