"""Cultural adaptation engine.

Applies Hofstede-style cultural dimensions to adapt content generation
directives for specific target markets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CulturalDirective:
    """Structured cultural directive for content generation.

    Contains Hofstede-inspired cultural dimensions that guide how content
    should be adapted for a specific market.
    """

    formality: float = 0.5  # 0=informal, 1=highly formal
    directness: float = 0.5  # 0=indirect/high-context, 1=direct/low-context
    individualism: float = 0.5  # 0=collectivist, 1=individualist
    humor: float = 0.3  # 0=avoid humor, 1=humor encouraged
    persuasion_style: str = "logical"  # "logical", "emotional", "authority", "social_proof"
    emotional_expression: float = 0.5  # 0=restrained, 1=expressive
    uncertainty_avoidance: float = 0.5  # 0=comfortable with ambiguity, 1=needs certainty
    target_market: str = ""
    content_type: str = ""
    brand_voice_id: str | None = None
    overrides: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "formality": self.formality,
            "directness": self.directness,
            "individualism": self.individualism,
            "humor": self.humor,
            "persuasion_style": self.persuasion_style,
            "emotional_expression": self.emotional_expression,
            "uncertainty_avoidance": self.uncertainty_avoidance,
            "target_market": self.target_market,
            "content_type": self.content_type,
            "brand_voice_id": self.brand_voice_id,
            "overrides": self.overrides,
        }


# Default cultural dimensions for common markets
# Based on Hofstede's cultural dimensions theory (simplified)
_DEFAULT_MARKET_DIMENSIONS: dict[str, dict[str, Any]] = {
    "en-US": {
        "formality": 0.3,
        "directness": 0.8,
        "individualism": 0.9,
        "humor": 0.5,
        "persuasion_style": "logical",
        "emotional_expression": 0.6,
        "uncertainty_avoidance": 0.3,
    },
    "en-GB": {
        "formality": 0.5,
        "directness": 0.6,
        "individualism": 0.8,
        "humor": 0.7,
        "persuasion_style": "logical",
        "emotional_expression": 0.4,
        "uncertainty_avoidance": 0.4,
    },
    "de-DE": {
        "formality": 0.7,
        "directness": 0.8,
        "individualism": 0.7,
        "humor": 0.2,
        "persuasion_style": "logical",
        "emotional_expression": 0.3,
        "uncertainty_avoidance": 0.7,
    },
    "fr-FR": {
        "formality": 0.7,
        "directness": 0.6,
        "individualism": 0.6,
        "humor": 0.4,
        "persuasion_style": "authority",
        "emotional_expression": 0.5,
        "uncertainty_avoidance": 0.6,
    },
    "ja-JP": {
        "formality": 0.8,
        "directness": 0.2,
        "individualism": 0.3,
        "humor": 0.3,
        "persuasion_style": "social_proof",
        "emotional_expression": 0.3,
        "uncertainty_avoidance": 0.8,
    },
    "zh-CN": {
        "formality": 0.6,
        "directness": 0.3,
        "individualism": 0.2,
        "humor": 0.3,
        "persuasion_style": "authority",
        "emotional_expression": 0.4,
        "uncertainty_avoidance": 0.6,
    },
    "es-ES": {
        "formality": 0.5,
        "directness": 0.5,
        "individualism": 0.5,
        "humor": 0.6,
        "persuasion_style": "emotional",
        "emotional_expression": 0.8,
        "uncertainty_avoidance": 0.5,
    },
    "pt-BR": {
        "formality": 0.4,
        "directness": 0.4,
        "individualism": 0.4,
        "humor": 0.6,
        "persuasion_style": "emotional",
        "emotional_expression": 0.8,
        "uncertainty_avoidance": 0.4,
    },
    "ar-SA": {
        "formality": 0.8,
        "directness": 0.3,
        "individualism": 0.3,
        "humor": 0.2,
        "persuasion_style": "authority",
        "emotional_expression": 0.6,
        "uncertainty_avoidance": 0.7,
    },
    "hi-IN": {
        "formality": 0.6,
        "directness": 0.4,
        "individualism": 0.3,
        "humor": 0.4,
        "persuasion_style": "social_proof",
        "emotional_expression": 0.7,
        "uncertainty_avoidance": 0.5,
    },
}


# Default dimensions for unknown markets
_DEFAULT_DIMENSIONS: dict[str, Any] = {
    "formality": 0.5,
    "directness": 0.5,
    "individualism": 0.5,
    "humor": 0.3,
    "persuasion_style": "logical",
    "emotional_expression": 0.5,
    "uncertainty_avoidance": 0.5,
}


class CulturalAdaptationEngine:
    """Engine for adapting content directives based on cultural dimensions.

    Uses Hofstede-inspired cultural dimensions to generate structured
    directives that guide LLM content generation for specific markets.
    """

    def __init__(
        self,
        custom_dimensions: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the cultural adaptation engine.

        Args:
            custom_dimensions: Optional custom market dimension overrides.
                Keys are market codes (e.g., "en-US"), values are dimension dicts.
        """
        self._dimensions = {**_DEFAULT_MARKET_DIMENSIONS}
        if custom_dimensions:
            self._dimensions.update(custom_dimensions)

    def _get_base_dimensions(self, market_code: str) -> dict[str, Any]:
        """Get base cultural dimensions for a market.

        Falls back to language-only code (e.g., "en" from "en-US") if
        exact match not found, then to global defaults.
        """
        if market_code in self._dimensions:
            return dict(self._dimensions[market_code])

        # Try language-only fallback
        lang = market_code.split("-")[0]
        for code, dims in self._dimensions.items():
            if code.startswith(f"{lang}-"):
                return dict(dims)

        return dict(_DEFAULT_DIMENSIONS)

    def adapt(
        self,
        target_market: str,
        content_type: str,
        brand_voice_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> CulturalDirective:
        """Generate a cultural directive for content generation.

        Args:
            target_market: Market code (e.g., "en-US", "de-DE")
            content_type: Type of content (e.g., "blog_post", "social_media", "email")
            brand_voice_id: Optional brand voice ID for tone consistency
            overrides: Optional dimension overrides to apply on top of market defaults

        Returns:
            CulturalDirective with adapted dimensions for the target market
        """
        overrides = overrides or {}

        # Start with base dimensions for the market
        dimensions = self._get_base_dimensions(target_market)

        # Apply content-type adjustments as deltas on top of market dimensions
        for key, delta in self._content_type_adjustments(content_type).items():
            if key in dimensions and isinstance(dimensions[key], (int, float)):
                dimensions[key] = max(0.0, min(1.0, dimensions[key] + delta))

        # Apply explicit overrides last (highest priority)
        dimensions.update(overrides)

        # Extract persuasion_style separately (it's a string, not a float)
        persuasion_style = dimensions.pop("persuasion_style", "logical")

        # Validate and clamp float dimensions to [0, 1]
        for key, value in dimensions.items():
            if isinstance(value, (int, float)):
                dimensions[key] = max(0.0, min(1.0, float(value)))

        return CulturalDirective(
            formality=dimensions.get("formality", 0.5),
            directness=dimensions.get("directness", 0.5),
            individualism=dimensions.get("individualism", 0.5),
            humor=dimensions.get("humor", 0.3),
            persuasion_style=persuasion_style,
            emotional_expression=dimensions.get("emotional_expression", 0.5),
            uncertainty_avoidance=dimensions.get("uncertainty_avoidance", 0.5),
            target_market=target_market,
            content_type=content_type,
            brand_voice_id=brand_voice_id,
            overrides=overrides,
        )

    def _content_type_adjustments(self, content_type: str) -> dict[str, float]:
        """Return dimension adjustments (deltas) based on content type.

        Values are deltas that get added to the market's base dimensions.
        Positive values increase the dimension, negative values decrease it.
        """
        adjustments: dict[str, dict[str, float]] = {
            "email": {"formality": 0.1, "directness": 0.1},
            "social_media": {"humor": 0.2, "emotional_expression": 0.1},
            "blog_post": {"formality": -0.1, "directness": 0.0},
            "press_release": {"formality": 0.2, "humor": -0.2},
            "ad_copy": {"emotional_expression": 0.2, "humor": 0.1},
            "product_description": {"directness": 0.1, "formality": -0.1},
            "legal": {"formality": 0.3, "humor": -0.3, "directness": -0.1},
        }

        return dict(adjustments.get(content_type, {}))

    def register_market(self, market_code: str, dimensions: dict[str, Any]) -> None:
        """Register or update cultural dimensions for a market.

        Args:
            market_code: Market code (e.g., "en-US")
            dimensions: Cultural dimensions dictionary
        """
        self._dimensions[market_code] = dimensions
