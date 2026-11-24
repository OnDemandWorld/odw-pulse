"""StorageClient — S3-compatible object storage connector.

TSD §2.12 — binary assets (generated images, exported documents, …) are
persisted in an S3-compatible store (MinIO in self-hosted deployments,
AWS S3 in cloud).  This client uses ``httpx`` to speak the S3 REST API
directly so we do not force a heavy ``boto3`` dependency on every
environment.  A ``boto3``-backed variant can be dropped in later without
changing the call-sites.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

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

    @staticmethod
    def _sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _signing_key(self, date_stamp: str) -> bytes:
        k_date = hmac.new(
            f"AWS4{self._secret_key}".encode(), date_stamp.encode(), hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, self._region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()

    def _sigv4_headers(
        self,
        method: str,
        url: str,
        payload: bytes,
        content_type: str | None = None,
    ) -> dict[str, str]:
        """AWS SigV4 header authentication (audit finding #85).

        Replaces the previous unauthenticated PUT/GET, which only worked
        against public buckets (MinIO/S3 reject them with 403).
        """
        parsed = urlsplit(url)
        now = dt.datetime.now(dt.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = self._sha256_hex(payload)

        headers = {
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type is not None:
            headers["content-type"] = content_type
        signed_headers = ";".join(sorted(headers))
        canonical_headers = "".join(
            f"{k}:{headers[k].strip()}\n" for k in sorted(headers)
        )
        canonical_query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}"
            for k, v in sorted(parse_qsl(parsed.query, keep_blank_values=True))
        )
        canonical_request = (
            f"{method}\n{parsed.path}\n{canonical_query}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
            f"{self._sha256_hex(canonical_request.encode())}"
        )
        signature = hmac.new(
            self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        result = {
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }
        if content_type is not None:
            result["Content-Type"] = content_type
        return result

    def _presign_params(self, key: str, expires: int) -> dict[str, str]:
        """SigV4 query-string presigning for temporary GET access.

        Audit finding #85: signs the SAME percent-encoded canonical
        resource that appears in the URL (the old V2-style demo signature
        used the raw key and mismatched for spaces/unicode).
        """
        url = self._object_url(key)
        parsed = urlsplit(url)
        now = dt.datetime.now(dt.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access_key}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}"
            for k, v in sorted(params.items())
        )
        canonical_request = (
            f"GET\n{parsed.path}\n{canonical_query}\n"
            f"host:{parsed.netloc}\n\nhost\nUNSIGNED-PAYLOAD"
        )
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
            f"{self._sha256_hex(canonical_request.encode())}"
        )
        signature = hmac.new(
            self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        return {**params, "X-Amz-Signature": signature}

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
        headers = self._sigv4_headers("PUT", url, data, content_type=content_type)
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
        headers = self._sigv4_headers("GET", url, b"")
        response = await self._http.get(url, headers=headers)
        response.raise_for_status()
        return response.content

    async def get_presigned_url(
        self,
        key: str,
        expires: int = 3600,
    ) -> str:
        """Return a presigned URL that grants temporary GET access to *key*."""
        params = self._presign_params(key, expires=expires)
        url = self._object_url(key)
        query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in params.items()
        )
        return f"{url}?{query}"
