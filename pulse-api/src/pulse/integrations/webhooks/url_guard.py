"""SSRF protection for outbound webhook URLs.

Webhook registration and test dispatch accept subscriber URLs.  Without
validation an authenticated user could point the server at cloud metadata
endpoints (``http://169.254.169.254/...``), loopback services, or anything
else on the internal network.

The guard rejects:

* non-http(s) schemes (``file://``, ``gopher://``, …) — in production only
  ``https`` is accepted;
* hostnames that resolve (even partially) to loopback, private, link-local,
  multicast, reserved, or unspecified addresses.

This is defence-in-depth: DNS can be re-bound between validation and
request time, so a determined attacker with control of DNS could still
bypass it.  For production environments the robust answer is egress
filtering at the network layer; see PLAN.md.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from pulse.config import get_settings

_ALLOWED_SCHEMES_DEV = ("http", "https")
_ALLOWED_SCHEMES_PROD = ("https",)


class WebhookURLBlockedError(ValueError):
    """Raised when a webhook URL fails SSRF validation."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return *True* for addresses that must never be webhook targets."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_webhook_url(url: str) -> None:
    """Validate *url* as a safe webhook destination.

    Raises:
        WebhookURLBlockedError: When the URL is malformed or points at a
            blocked scheme, host, or address range.
    """
    parsed = urlparse(url)

    settings = get_settings()
    allowed = _ALLOWED_SCHEMES_PROD if settings.is_production else _ALLOWED_SCHEMES_DEV
    if parsed.scheme not in allowed:
        raise WebhookURLBlockedError(
            f"Webhook scheme '{parsed.scheme or 'none'}' is not allowed "
            f"(allowed: {', '.join(allowed)})"
        )

    host = parsed.hostname
    if not host:
        raise WebhookURLBlockedError("Webhook URL has no host")

    # Resolve the host and inspect every address it maps to.  For IP
    # literals getaddrinfo simply returns the literal itself.
    try:
        addr_info = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebhookURLBlockedError(f"Cannot resolve webhook host '{host}'") from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise WebhookURLBlockedError(
                f"Webhook host '{host}' resolves to a blocked address ({ip})"
            )


__all__ = ["WebhookURLBlockedError", "validate_webhook_url"]
