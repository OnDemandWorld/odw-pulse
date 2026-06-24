"""LLM abstraction layer for Pulse.

This module provides a unified interface for interacting with multiple
LLM providers (OpenAI, Anthropic, Ollama) with automatic fallback routing.
"""

from pulse.llm.base import LLMProvider, LLMResponse
from pulse.llm.fallback_router import CircuitBreakerConfig, CircuitState, FallbackRouter
from pulse.llm.registry import ProviderRegistry, get_registry, reset_registry

__all__ = [
    "CircuitBreakerConfig",
    "CircuitState",
    "FallbackRouter",
    "LLMProvider",
    "LLMResponse",
    "ProviderRegistry",
    "get_registry",
    "reset_registry",
]
