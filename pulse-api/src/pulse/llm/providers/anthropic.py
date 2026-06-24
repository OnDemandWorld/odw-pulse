"""Anthropic provider adapter using httpx (no SDK dependency)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from pulse.llm.base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider using httpx for HTTP requests.

    Supports the Anthropic Messages API with configurable model,
    temperature, max tokens, and other parameters.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60.0,
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Default model to use
            base_url: Anthropic API base URL
            timeout: Request timeout in seconds
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._client

    async def generate(self, prompt: str, params: dict[str, Any] | None = None) -> LLMResponse:
        """Generate text using Anthropic Messages API.

        Args:
            prompt: The input prompt
            params: Optional parameters (model, temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text and metadata
        """
        params = params or {}
        model = params.get("model", self._model)
        temperature = params.get("temperature", 0.7)
        max_tokens = params.get("max_tokens", 1024)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add optional parameters
        for key in ("top_p", "top_k", "stop_sequences"):
            if key in params:
                payload[key] = params[key]

        client = self._get_client()
        start_time = time.time()

        try:
            response = await client.post("/messages", json=payload)
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Extract text from response
            content = data.get("content", [])
            text = ""
            if content and isinstance(content, list):
                text = content[0].get("text", "")

            # Extract usage
            usage_data = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            }

            return LLMResponse(
                text=text,
                model=data.get("model", model),
                usage=usage,
                latency_ms=latency_ms,
                finish_reason=data.get("stop_reason", "end_turn"),
                metadata={"id": data.get("id", ""), "provider": "anthropic"},
            )
        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            return LLMResponse(
                text="",
                model=model,
                latency_ms=latency_ms,
                finish_reason="error",
                metadata={"error": str(e), "status_code": e.response.status_code},
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return LLMResponse(
                text="",
                model=model,
                latency_ms=latency_ms,
                finish_reason="error",
                metadata={"error": str(e)},
            )

    async def health(self) -> bool:
        """Check if Anthropic API is accessible (limited health check)."""
        # Anthropic doesn't have a public health endpoint, so we just check
        # if we can make a minimal request
        return True

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
