"""Pydantic models for generation requests and results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """Request model for content generation.

    Attributes:
        content_type: Type of content to generate (e.g., "blog_post", "email")
        target_market: Target market code (e.g., "en-US", "de-DE")
        brand_voice_id: Optional brand voice ID for tone consistency
        prompt: The user's generation prompt / instructions
        vault_sources: Optional list of source texts to reference
        glossary: Optional glossary terms to enforce
        llm_params: Optional LLM generation parameters
        cultural_overrides: Optional cultural dimension overrides
    """

    content_type: str = Field(..., description="Type of content to generate")
    target_market: str = Field(..., description="Target market code (ISO 639-1 + region)")
    brand_voice_id: str | None = Field(None, description="Optional brand voice ID")
    prompt: str = Field(..., description="User's generation prompt or instructions")
    vault_sources: list[str] = Field(default_factory=list, description="Source texts to reference")
    glossary: list[dict[str, Any]] = Field(
        default_factory=list, description="Glossary terms to enforce"
    )
    llm_params: dict[str, Any] = Field(
        default_factory=dict, description="LLM generation parameters"
    )
    cultural_overrides: dict[str, Any] = Field(
        default_factory=dict, description="Cultural dimension overrides"
    )


class GenerationResult(BaseModel):
    """Result model for content generation.

    Attributes:
        content: The generated text content
        quality_score: Quality score from 0 to 100
        quality_flags: List of quality issue flags
        cultural_directive: Cultural adaptation details applied
        llm_model: The LLM model used for generation
        llm_usage: Token usage information
        latency_ms: Total generation latency in milliseconds
    """

    content: str = Field(..., description="Generated text content")
    quality_score: int = Field(..., ge=0, le=100, description="Quality score (0-100)")
    quality_flags: list[str] = Field(default_factory=list, description="Quality issue flags")
    cultural_directive: dict[str, Any] = Field(
        default_factory=dict, description="Cultural adaptation details"
    )
    llm_model: str = Field(..., description="LLM model used")
    llm_usage: dict[str, int] = Field(default_factory=dict, description="Token usage")
    latency_ms: float = Field(..., description="Total latency in milliseconds")
