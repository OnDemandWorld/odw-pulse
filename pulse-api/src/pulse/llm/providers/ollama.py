"""Ollama provider adapter for local model inference."""

from __future__ import annotations

import time
from typing import Any

import httpx

from pulse.llm.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """Ollama local model provider using httpx for HTTP requests.

    Supports running models locally via Ollama's REST API.
    """

    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            model: Default model to use (e.g., "llama3.1", "mistral")
            base_url: Ollama API base URL
            timeout: Request timeout in seconds (longer for local inference)
        """
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "ollama"

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
        return self._client

    async def generate(self, prompt: str, params: dict[str, Any] | None = None) -> LLMResponse:
        """Generate text using Ollama API.

        Args:
            prompt: The input prompt
            params: Optional parameters (model, temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text and metadata
        """
        params = params or {}
        model = params.get("model", self._model)
        temperature = params.get("temperature", 0.7)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        # Add optional parameters
        if "max_tokens" in params:
            payload["options"]["num_predict"] = params["max_tokens"]
        if "top_p" in params:
            payload["options"]["top_p"] = params["top_p"]

        client = self._get_client()
        start_time = time.time()

        try:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            text = data.get("response", "")

            # Extract usage if available
            usage = {}
            if "prompt_eval_count" in data:
                usage["prompt_tokens"] = data["prompt_eval_count"]
            if "eval_count" in data:
                usage["completion_tokens"] = data["eval_count"]
            if usage:
                usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

            return LLMResponse(
                text=text,
                model=data.get("model", model),
                usage=usage,
                latency_ms=latency_ms,
                finish_reason="stop" if data.get("done", False) else "length",
                metadata={"provider": "ollama"},
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
        """Check if Ollama service is accessible."""
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
