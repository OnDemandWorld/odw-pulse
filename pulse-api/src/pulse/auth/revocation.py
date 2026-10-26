"""Server-side JWT revocation (BUILD_REPORT C-4).

Access tokens used to be valid until ``exp`` no matter what happened on
the server — "logout" was a client-side ``localStorage`` removal, so a
stolen token stayed live.  This module adds two revocation mechanisms on
top of the shared KV store:

* **Per-token** blocklist keyed by the ``jti`` claim.  ``POST /auth/logout``
  writes a marker whose TTL equals the token's remaining lifetime — the
  marker never outlives the token it revokes, so the keyspace self-cleans.
* **Per-user** "revoke everything issued up to now" cutoff.
  ``POST /auth/logout-everywhere`` stores ``floor(now) + 1``; tokens whose
  ``iat`` is strictly earlier are rejected.  Second-granular ``iat`` makes
  the exact current second ambiguous, so the cutoff is conservative: it
  also rejects fresh tokens minted within the same second as the call.

State lives in Redis when reachable (so revocation is visible to every
API replica) and degrades to the in-process fallback otherwise.  A
multi-replica deployment *with Redis down* therefore tolerates a token
revoked on replica A still working briefly on replica B — fail-soft by
design, mirroring job dispatch's in-process fallback.
"""

from __future__ import annotations

import time
import uuid

from pulse.config import get_settings
from pulse.core.redis_kv import get_kv_store

_JTI_KEY = "pulse:revoked:jti:{jti}"
_USER_KEY = "pulse:revoked:user:{user_id}"


def _cutoff_ttl_seconds() -> int:
    """How long a user-wide cutoff must live: the full token lifetime plus margin."""
    return get_settings().jwt_access_token_expire_minutes * 60 + 120


def remaining_token_ttl(exp: int | None) -> int:
    """Seconds until *exp* (unix), floored at 1; falls back to the full lifetime."""
    if exp is None:
        return get_settings().jwt_access_token_expire_minutes * 60 + 60
    return max(exp - int(time.time()), 1)


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Blocklist the token identified by *jti* until it would expire."""
    await get_kv_store().set(_JTI_KEY.format(jti=jti), "1", ttl_seconds)


async def is_token_revoked(jti: str) -> bool:
    """True if *jti* was individually revoked and has not expired yet."""
    return (await get_kv_store().get(_JTI_KEY.format(jti=jti))) is not None


async def revoke_all_tokens(user_id: uuid.UUID) -> None:
    """Reject every token issued at or before the current second for *user_id*."""
    cutoff = int(time.time()) + 1
    await get_kv_store().set(
        _USER_KEY.format(user_id=user_id), str(cutoff), _cutoff_ttl_seconds()
    )


async def is_token_revoked_by_logout_all(user_id: uuid.UUID, issued_at: int | None) -> bool:
    """True if *issued_at* predates a ``logout-everywhere`` cutoff for the user.

    Tokens without an ``iat`` claim (legacy) are left to the other checks.
    """
    if issued_at is None:
        return False
    raw = await get_kv_store().get(_USER_KEY.format(user_id=user_id))
    if raw is None:
        return False
    try:
        cutoff = int(raw)
    except ValueError:  # pragma: no cover - corrupted store entry
        return False
    return issued_at < cutoff


__all__ = [
    "is_token_revoked",
    "is_token_revoked_by_logout_all",
    "remaining_token_ttl",
    "revoke_all_tokens",
    "revoke_token",
]
