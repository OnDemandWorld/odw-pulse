"""LLM provider registry.

Provides a global registry for LLM providers, allowing the application
to register, retrieve, and list available providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pulse.llm.base import LLMProvider

if TYPE_CHECKING:
    from pulse.config import Settings


class ProviderRegistry:
    """Registry for LLM providers.

    Maintains a mapping of provider names to provider instances,
    allowing dynamic registration and lookup.
    """

    def __init__(self) -> None:
        """Initialize an empty provider registry."""
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        """Register a provider under the given name.

        Args:
            name: Unique identifier for the provider
            provider: The LLMProvider instance to register

        Raises:
            ValueError: If a provider with this name is already registered
        """
        if name in self._providers:
            raise ValueError(f"Provider '{name}' is already registered")
        self._providers[name] = provider

    def get(self, name: str) -> LLMProvider:
        """Retrieve a provider by name.

        Args:
            name: The provider name to look up

        Returns:
            The LLMProvider instance

        Raises:
            KeyError: If no provider with this name is registered
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not registered")
        return self._providers[name]

    def list_providers(self) -> list[str]:
        """Return a list of all registered provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def unregister(self, name: str) -> None:
        """Remove a provider from the registry.

        Args:
            name: The provider name to remove

        Raises:
            KeyError: If no provider with this name is registered
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not registered")
        del self._providers[name]

    def clear(self) -> None:
        """Remove all providers from the registry."""
        self._providers.clear()


# Global singleton registry instance
_global_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """Get the global provider registry singleton.

    Returns:
        The global ProviderRegistry instance
    """
    global _global_registry  # noqa: PLW0603
    if _global_registry is None:
        _global_registry = ProviderRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (primarily for testing)."""
    global _global_registry  # noqa: PLW0603
    if _global_registry is not None:
        _global_registry.clear()
    _global_registry = None


def bootstrap_providers_from_settings(settings: Settings | None = None) -> ProviderRegistry:
    """Register providers configured via settings into the global registry.

    Idempotent: already-registered providers are left untouched. Registration
    order is deterministic (openai, anthropic, ollama) so primary/secondary
    selection never depends on accidental dict ordering. Called lazily by the
    generation orchestrator factory, covering both the API and worker paths.

    Args:
        settings: Optional settings override (defaults to get_settings()).

    Returns:
        The global registry, populated with every configured provider.
    """
    from pulse.config import get_settings
    from pulse.llm.providers.anthropic import AnthropicProvider
    from pulse.llm.providers.ollama import OllamaProvider
    from pulse.llm.providers.openai import OpenAIProvider

    s = settings or get_settings()
    registry = get_registry()
    registered = registry.list_providers()
    if s.openai_api_key and "openai" not in registered:
        registry.register("openai", OpenAIProvider(api_key=s.openai_api_key))
    if s.anthropic_api_key and "anthropic" not in registered:
        registry.register("anthropic", AnthropicProvider(api_key=s.anthropic_api_key))
    if s.ollama_base_url and "ollama" not in registered:
        registry.register("ollama", OllamaProvider(base_url=s.ollama_base_url))
    return registry
