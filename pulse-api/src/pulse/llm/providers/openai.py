"""OpenAI provider adapter using httpx (no SDK dependency)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from pulse.llm.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI API provider using httpx for HTTP requests.

    Supports the OpenAI Chat Completions API with configurable model,
    temperature, max tokens, and other parameters.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ) -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Default model to use (e.g., "gpt-4o-mini", "gpt-4o")
            base_url: OpenAI API base URL
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
        return "openai"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._client

    async def generate(self, prompt: str, params: dict[str, Any] | None = None) -> LLMResponse:
        """Generate text using OpenAI Chat Completions API.

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
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add optional parameters
        for key in ("top_p", "frequency_penalty", "presence_penalty", "stop"):
            if key in params:
                payload[key] = params[key]

        client = self._get_client()
        start_time = time.time()

        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Extract text from response
            choices = data.get("choices", [])
            text = ""
            finish_reason = "stop"
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                finish_reason = choices[0].get("finish_reason", "stop")

            # Extract usage
            usage_data = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

            return LLMResponse(
                text=text,
                model=data.get("model", model),
                usage=usage,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                metadata={"id": data.get("id", ""), "provider": "openai"},
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
        """Check if OpenAI API is accessible."""
        try:
            client = self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
