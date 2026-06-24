"""Market profile loader and cache.

Provides functions to load market profiles from the database with
in-memory caching to avoid repeated DB queries.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.models.market_profile import MarketProfile

# In-memory cache for market profiles
_cache: dict[str, dict[str, Any]] = {}
_cache_enabled: bool = True


def set_cache_enabled(enabled: bool) -> None:
    """Enable or disable the market profile cache."""
    global _cache_enabled  # noqa: PLW0603
    _cache_enabled = enabled


def clear_cache() -> None:
    """Clear the market profile cache."""
    _cache.clear()


async def load_market_profile(
    session: AsyncSession,
    market_code: str,
) -> dict[str, Any] | None:
    """Load a market profile from the database by code.

    Uses in-memory cache to avoid repeated queries for the same market.

    Args:
        session: Async SQLAlchemy session
        market_code: ISO 639-1 language code (e.g., "en-US", "de-DE")

    Returns:
        Dictionary with market profile data, or None if not found
    """
    # Check cache first
    if _cache_enabled and market_code in _cache:
        return _cache[market_code]

    # Query database
    result = await session.execute(
        select(MarketProfile).where(
            MarketProfile.code == market_code,
            MarketProfile.is_active.is_(True),
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        return None

    data = {
        "id": str(profile.id),
        "code": profile.code,
        "name": profile.name,
        "cultural_dimensions": profile.cultural_dimensions or {},
        "fallback_code": profile.fallback_code,
        "is_active": profile.is_active,
    }

    # Cache the result
    if _cache_enabled:
        _cache[market_code] = data

    return data


async def load_market_profile_with_fallback(
    session: AsyncSession,
    market_code: str,
) -> dict[str, Any] | None:
    """Load a market profile, following the fallback chain if needed.

    If the requested market is not found, attempts to load the fallback
    market specified by fallback_code.

    Args:
        session: Async SQLAlchemy session
        market_code: Market code to look up

    Returns:
        Dictionary with market profile data, or None if not found
    """
    profile = await load_market_profile(session, market_code)
    if profile is not None:
        return profile

    # Try loading from cache to find fallback_code
    if _cache_enabled and market_code in _cache:
        cached = _cache[market_code]
        fallback = cached.get("fallback_code")
        if fallback:
            return await load_market_profile(session, fallback)

    return None


async def list_active_markets(session: AsyncSession) -> list[dict[str, Any]]:
    """List all active market profiles.

    Args:
        session: Async SQLAlchemy session

    Returns:
        List of market profile dictionaries
    """
    result = await session.execute(
        select(MarketProfile).where(MarketProfile.is_active.is_(True))
    )
    profiles = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
            "cultural_dimensions": p.cultural_dimensions or {},
            "fallback_code": p.fallback_code,
            "is_active": p.is_active,
        }
        for p in profiles
    ]
