"""Pydantic models for generation requests and results."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class GenerationError(RuntimeError):
    """Raised when the LLM provider fails to produce content.

    Carries the provider-reported HTTP status code (when available) so
    callers can distinguish upstream failures from internal errors.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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

    @field_validator("content_type")
    @classmethod
    def _safe_content_type(cls, v: str) -> str:
        # Audit finding #13: this value is interpolated into the system
        # prompt; reject newlines/control characters and injection payloads.
        if not re.fullmatch(r"[A-Za-z0-9_\- ]{1,64}", v):
            raise ValueError(
                "content_type must be 1-64 chars of letters, digits, '_', '-' or space"
            )
        return v

    @field_validator("target_market")
    @classmethod
    def _safe_target_market(cls, v: str) -> str:
        # Audit finding #13: locale-shaped codes only (e.g. en-US, zh-Hant-TW).
        if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", v):
            raise ValueError("target_market must be a locale code like 'en-US'")
        return v


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
