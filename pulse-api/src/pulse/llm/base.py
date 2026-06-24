"""LLM provider abstraction layer.

Defines the base interface that all LLM providers must implement,
plus the response dataclass returned by providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM provider.

    Attributes:
        text: The generated text content
        model: The model identifier that generated the response
        usage: Token usage information (prompt_tokens, completion_tokens, total_tokens)
        latency_ms: Time taken to generate the response in milliseconds
        finish_reason: Why generation stopped (e.g., "stop", "length", "error")
        metadata: Additional provider-specific metadata
    """

    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers (OpenAI, Anthropic, Ollama, etc.) must implement
    this interface to be used with the Pulse generation engine.
    """

    @abstractmethod
    async def generate(self, prompt: str, params: dict[str, Any] | None = None) -> LLMResponse:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt to send to the LLM
            params: Optional generation parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse containing the generated text and metadata
        """

    @abstractmethod
    async def health(self) -> bool:
        """Check if the provider is healthy and available.

        Returns:
            True if the provider is ready to accept requests, False otherwise
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'anthropic')."""
