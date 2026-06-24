"""Deterministic variant assignment (TSD §4.15)."""

from __future__ import annotations

import contextlib
import hashlib
from typing import Any


def assign_variant(
    visitor_id: str,
    experiment_id: str,
    weights: dict[str, float],
) -> str:
    """Assign a visitor to a variant deterministically.

    Uses SHA256(visitor_id + experiment_id) % 100 to get a bucket (0-99),
    then maps that bucket to a variant based on cumulative weights.

    Args:
        visitor_id: Opaque visitor identifier (user ID, session ID, etc.)
        experiment_id: Experiment identifier
        weights: Dict mapping variant names to their relative weights.
                 Weights are normalized internally.

    Returns:
        The variant name assigned to this visitor.

    Example:
        >>> assign_variant("user123", "exp456", {"control": 0.5, "treatment": 0.5})
        'control'
    """
    if not weights:
        raise ValueError("weights dict must not be empty")

    # Deterministic hash
    hash_input = f"{visitor_id}{experiment_id}"
    hash_bytes = hashlib.sha256(hash_input.encode("utf-8")).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
    bucket = hash_int % 100

    # Normalize weights
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("Total weight must be positive")

    normalized = {k: v / total_weight for k, v in weights.items()}

    # Map bucket to variant via cumulative distribution
    cumulative = 0.0
    sorted_variants = sorted(normalized.items(), key=lambda x: x[0])  # Sort for determinism

    for variant_name, weight in sorted_variants:
        cumulative += weight
        if bucket < cumulative * 100:
            return variant_name

    # Fallback (should never reach here due to normalization)
    return sorted_variants[-1][0]


def assign_variant_with_cache(
    visitor_id: str,
    experiment_id: str,
    weights: dict[str, float],
    redis_client: Any = None,
    cache_ttl: int = 86400,
) -> str:
    """Assign variant with optional Redis caching.

    If redis_client is provided, checks cache first. If not found,
    computes assignment and stores in cache.

    Args:
        visitor_id: Opaque visitor identifier
        experiment_id: Experiment identifier
        weights: Variant weights
        redis_client: Optional Redis client instance
        cache_ttl: Cache TTL in seconds (default 24 hours)

    Returns:
        The variant name
    """
    if redis_client is None:
        return assign_variant(visitor_id, experiment_id, weights)

    cache_key = f"experiment:assignment:{experiment_id}:{visitor_id}"

    # Try cache
    try:
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached.decode("utf-8") if isinstance(cached, bytes) else cached
    except Exception:
        # Cache miss or error, compute assignment
        pass

    # Compute
    variant = assign_variant(visitor_id, experiment_id, weights)

    # Store in cache
    with contextlib.suppress(Exception):
        redis_client.setex(cache_key, cache_ttl, variant)

    return variant
