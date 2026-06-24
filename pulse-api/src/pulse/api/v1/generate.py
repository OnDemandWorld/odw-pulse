"""Content generation endpoints (TSD §2).

* ``POST /generate``       — generate content synchronously
* ``POST /generate/stream`` — generate content with SSE streaming (stub)
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from pulse.generation.models import GenerationRequest, GenerationResult
from pulse.generation.orchestrator import GenerationOrchestrator
from pulse.llm import FallbackRouter, get_registry
from pulse.llm.fallback_router import CircuitBreakerConfig

router = APIRouter(tags=["generation"])

# Global orchestrator instance (initialized lazily)
_orchestrator: GenerationOrchestrator | None = None


def get_orchestrator() -> GenerationOrchestrator:
    """Get or create the global generation orchestr."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        # Set up fallback router with default providers
        registry = get_registry()

        # Try to get providers from registry, or create mock ones for now
        primary = None
        secondary = None

        providers = registry.list_providers()
        if len(providers) >= 2:
            primary = registry.get(providers[0])
            secondary = registry.get(providers[1])
        elif len(providers) == 1:
            primary = registry.get(providers[0])
            # Use same provider as secondary for now
            secondary = primary
        else:
            # No providers registered — this will fail at generation time
            raise RuntimeError(
                "No LLM providers registered. "
                "Configure OPENAI_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_BASE_URL."
            )

        fallback_router = FallbackRouter(
            primary=primary,
            secondary=secondary,
            config=CircuitBreakerConfig(),
        )

        _orchestrator = GenerationOrchestrator(fallback_router=fallback_router)

    return _orchestrator


@router.post("/generate", response_model=GenerationResult)
async def generate(request: GenerationRequest) -> GenerationResult:
    """Generate content based on the provided request.

    Accepts a GenerationRequest with content type, target market, prompt,
    and optional configuration. Returns generated content with quality score.

    Args:
        request: The generation request

    Returns:
        GenerationResult with content, quality score, and metadata
    """
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.generate(request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        ) from e


@router.post("/generate/stream")
async def generate_stream(request: GenerationRequest) -> StreamingResponse:
    """Generate content with Server-Sent Events streaming (stub).

    This endpoint is a stub for future streaming implementation.
    Currently returns the full response as a single SSE event.

    Args:
        request: The generation request

    Returns:
        StreamingResponse with SSE events
    """
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.generate(request)

        # Convert to SSE format (stub — single event)
        async def event_generator() -> Any:
            data = {
                "type": "content",
                "content": result.content,
                "quality_score": result.quality_score,
                "done": True,
            }
            yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming generation failed: {str(e)}",
        ) from e


def reset_orchestrator() -> None:
    """Reset the orchestrator (for testing)."""
    global _orchestrator  # noqa: PLW0603
    _orchestrator = None
