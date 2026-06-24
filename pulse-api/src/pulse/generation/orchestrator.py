"""Generation orchestrator — coordinates the full generation pipeline.

The orchestrator chains together market profile loading, brand voice lookup,
cultural adaptation, prompt composition, LLM invocation, and quality scoring
to produce the final generated content.
"""

from __future__ import annotations

import time
from typing import Any

from pulse.cultural.engine import CulturalAdaptationEngine
from pulse.cultural.market_profile import load_market_profile
from pulse.generation.models import GenerationRequest, GenerationResult
from pulse.llm.fallback_router import FallbackRouter
from pulse.prompts.composer import PromptComposer
from pulse.quality.engine import QualityScoringEngine

# Default system prompt template
_DEFAULT_SYSTEM_TEMPLATE = (
    "You are a professional content writer specializing in {content_type} content "
    "for the {target_market} market.\n\n"
    "Cultural Guidelines:\n"
    "- Formality level: {formality}/1.0\n"
    "- Directness: {directness}/1.0\n"
    "- Individualism: {individualism}/1.0\n"
    "- Humor: {humor}/1.0\n"
    "- Persuasion style: {persuasion_style}\n"
    "- Emotional expression: {emotional_expression}/1.0\n"
    "- Uncertainty avoidance: {uncertainty_avoidance}/1.0\n"
    "{brand_voice_section}"
)

# Default user prompt template
_DEFAULT_USER_TEMPLATE = (
    "Generate {content_type} content for the {target_market} market.\n\n"
    "Instructions: {prompt}\n"
    "{vault_section}"
    "{glossary_section}"
)


class GenerationOrchestrator:
    """Orchestrates the full content generation pipeline.

    Coordinates market profile loading, cultural adaptation, prompt composition,
    LLM selection via fallback router, and quality scoring.
    """

    def __init__(
        self,
        fallback_router: FallbackRouter,
        cultural_engine: CulturalAdaptationEngine | None = None,
        prompt_composer: PromptComposer | None = None,
        quality_engine: QualityScoringEngine | None = None,
        db_session_factory: Any = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            fallback_router: Router for selecting LLM provider with fallback
            cultural_engine: Cultural adaptation engine (uses default if None)
            prompt_composer: Prompt composer (uses default if None)
            quality_engine: Quality scoring engine (uses default if None)
            db_session_factory: Async session factory for database access
        """
        self._router = fallback_router
        self._cultural_engine = cultural_engine or CulturalAdaptationEngine()
        self._composer = prompt_composer or PromptComposer()
        self._quality_engine = quality_engine or QualityScoringEngine()
        self._db_session_factory = db_session_factory

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Execute the full generation pipeline.

        Steps:
        1. Load market profile (if DB session available)
        2. Load brand voice (if brand_voice_id provided)
        3. Run cultural adaptation to get dimensions
        4. Compose system and user prompts
        5. Select LLM provider via fallback router
        6. Call provider to generate content
        7. Run quality scoring on generated content
        8. Return GenerationResult

        Args:
            request: The generation request

        Returns:
            GenerationResult with content, quality score, and metadata
        """
        start_time = time.time()

        # Step 1 & 2: Load market profile and brand voice (if DB available)
        market_dimensions: dict[str, Any] = {}
        brand_voice_data: dict[str, Any] = {}

        if self._db_session_factory:
            async with self._db_session_factory() as session:
                if request.target_market:
                    profile = await load_market_profile(session, request.target_market)
                    if profile:
                        market_dimensions = profile.get("cultural_dimensions", {})

        # Step 3: Run cultural adaptation
        cultural_directive = self._cultural_engine.adapt(
            target_market=request.target_market,
            content_type=request.content_type,
            brand_voice_id=request.brand_voice_id,
            overrides={**market_dimensions, **request.cultural_overrides},
        )

        # Build brand voice section for prompt
        brand_voice_section = ""
        if brand_voice_data:
            tone = brand_voice_data.get("tone_profile", {})
            if tone:
                brand_voice_section = f"\nBrand Voice: {tone.get('description', '')}\n"

        # Step 4: Compose prompts
        context = {
            "content_type": request.content_type,
            "target_market": request.target_market,
            "prompt": request.prompt,
            **cultural_directive.to_dict(),
            "brand_voice_section": brand_voice_section,
            "vault_section": self._format_vault_section(request.vault_sources),
            "glossary_section": self._format_glossary_section(request.glossary),
        }

        composed = self._composer.compose(
            _DEFAULT_SYSTEM_TEMPLATE,
            _DEFAULT_USER_TEMPLATE,
            context,
        )

        full_prompt = f"{composed['system']}\n\n{composed['user']}"

        # Step 5: Select LLM provider via fallback router
        provider = await self._router.route_request()

        # Step 6: Call provider
        llm_response = await provider.generate(full_prompt, request.llm_params)

        # Record success/failure for circuit breaker
        if llm_response.finish_reason == "error":
            await self._router.record_failure()
        else:
            await self._router.record_success()

        # Step 7: Run quality scoring
        quality_result = self._quality_engine.score(
            content=llm_response.text,
            vault_sources=request.vault_sources,
            glossary=request.glossary,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Step 8: Return result
        return GenerationResult(
            content=llm_response.text,
            quality_score=quality_result.score,
            quality_flags=quality_result.flags,
            cultural_directive=cultural_directive.to_dict(),
            llm_model=llm_response.model,
            llm_usage=llm_response.usage,
            latency_ms=latency_ms,
        )

    def _format_vault_section(self, vault_sources: list[str]) -> str:
        """Format vault sources for inclusion in prompt."""
        if not vault_sources:
            return ""

        sources_text = "\n".join(f"- {source}" for source in vault_sources)
        return f"\nReference Sources:\n{sources_text}\n"

    def _format_glossary_section(self, glossary: list[dict[str, Any]]) -> str:
        """Format glossary terms for inclusion in prompt."""
        if not glossary:
            return ""

        terms_text = "\n".join(
            f"- {term.get('term', '')}: {term.get('definition', '')}"
            for term in glossary
            if term.get("term")
        )
        return f"\nGlossary Terms to Use:\n{terms_text}\n"
