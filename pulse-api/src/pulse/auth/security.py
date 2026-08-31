"""Security utilities: JWT token management and password hashing.

Uses ``python-jose`` for JWT and ``bcrypt`` for password hashing.
bcrypt is required for creating new password hashes; a legacy SHA-256 based
scheme is still recognised (but never written) for backwards compatibility.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt  # type: ignore[import-untyped]

from pulse.config import get_settings

# ---------------------------------------------------------------------------
# bcrypt is a hard requirement for hashing new passwords (it is a declared
# dependency via passlib[bcrypt]).  A legacy single-iteration SHA-256 scheme
# ("plain:...") is still *verified* for backwards compatibility, but never
# created anymore.
# ---------------------------------------------------------------------------
try:
    import bcrypt as _bcrypt

    _HAS_BCRYPT = True
except ImportError:  # pragma: no cover - only in stripped environments
    _HAS_BCRYPT = False


# ---- Password hashing ----------------------------------------------------


def hash_password(password: str) -> str:
    """Return a secure bcrypt hash of *password*.

    Raises:
        RuntimeError: If bcrypt is not installed.  Falling back to a weak
            scheme silently would be a security footgun, so fail loudly.
    """
    if not _HAS_BCRYPT:
        raise RuntimeError(
            "bcrypt is required for password hashing — install passlib[bcrypt]"
        )
    salt = _bcrypt.gensalt()
    hashed: bytes = _bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check *plain_password* against *hashed_password*."""
    if _HAS_BCRYPT and hashed_password.startswith("$2"):
        return _bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    if hashed_password.startswith("plain:"):
        # Legacy fallback scheme — verify in constant time.
        _, salt_str, expected_hash = hashed_password.split(":", 2)
        actual = hashlib.sha256((salt_str + plain_password).encode()).hexdigest()
        return hmac.compare_digest(actual, expected_hash)
    return False


# ---- JWT tokens ----------------------------------------------------------


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    workspace_id: uuid.UUID,
    role: str,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "email": email,
        "role": role,
        "exp": expire,
        "iat": now,
    }
    return str(jwt.encode(payload, settings.pulse_secret_key, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Returns the payload as a ``dict[str, Any]``.

    Raises:
        JWTError: If the token is invalid or expired.
    """
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.pulse_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return payload


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
