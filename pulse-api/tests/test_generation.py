"""Tests for the core generation engine (TSD §2)."""

from __future__ import annotations

from typing import Any

import pytest

from pulse.cultural.engine import CulturalAdaptationEngine
from pulse.generation.models import GenerationRequest
from pulse.generation.orchestrator import GenerationOrchestrator
from pulse.llm.base import LLMProvider, LLMResponse
from pulse.llm.fallback_router import CircuitBreakerConfig, FallbackRouter
from pulse.quality.engine import QualityScoringEngine

# ---------------------------------------------------------------------------
# Mock LLM provider for testing
# ---------------------------------------------------------------------------


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(
        self,
        name: str = "mock",
        response_text: str = "Mock generated content that is long enough to pass quality checks.",
        should_fail: bool = False,
    ) -> None:
        self._name = name
        self._response_text = response_text
        self._should_fail = should_fail
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def generate(self, prompt: str, params: dict[str, Any] | None = None) -> LLMResponse:
        self.call_count += 1
        if self._should_fail:
            return LLMResponse(
                text="",
                model="mock-fail",
                latency_ms=10.0,
                finish_reason="error",
                metadata={"error": "Mock failure"},
            )
        return LLMResponse(
            text=self._response_text,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=50.0,
            finish_reason="stop",
        )

    async def health(self) -> bool:
        return not self._should_fail


# ---------------------------------------------------------------------------
# Test: generate returns content
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_returns_content() -> None:
    """Test that generation orchestrator returns generated content."""
    mock_provider = MockLLMProvider(
        response_text="This is a high-quality blog post about AI for the US market."
    )
    router = FallbackRouter(primary=mock_provider, secondary=mock_provider)
    orchestrator = GenerationOrchestrator(fallback_router=router)

    request = GenerationRequest(
        content_type="blog_post",
        target_market="en-US",
        prompt="Write about artificial intelligence",
    )

    result = await orchestrator.generate(request)

    assert result.content == "This is a high-quality blog post about AI for the US market."
    assert result.quality_score >= 0
    assert result.quality_score <= 100
    assert result.llm_model == "mock-model"
    assert result.llm_usage["total_tokens"] == 30
    assert result.latency_ms >= 0
    assert mock_provider.call_count == 1


# ---------------------------------------------------------------------------
# Test: cultural adaptation overrides
# ---------------------------------------------------------------------------


def test_cultural_adaptation_overrides() -> None:
    """Test that cultural adaptation applies overrides correctly."""
    engine = CulturalAdaptationEngine()

    # Test with explicit overrides
    directive = engine.adapt(
        target_market="en-US",
        content_type="email",
        overrides={"formality": 0.9, "humor": 0.1},
    )

    assert directive.target_market == "en-US"
    assert directive.content_type == "email"
    assert directive.formality == 0.9
    assert directive.humor == 0.1
    # directness should be from en-US defaults + email adjustment + override not set
    assert directive.directness >= 0.0
    assert directive.directness <= 1.0

    # Test without overrides — should use market defaults
    directive_default = engine.adapt(
        target_market="de-DE",
        content_type="blog_post",
    )

    assert directive_default.target_market == "de-DE"
    # German market has higher formality by default
    assert directive_default.formality > 0.5


# ---------------------------------------------------------------------------
# Test: quality score range
# ---------------------------------------------------------------------------


def test_quality_score_range() -> None:
    """Test that quality score is always in [0, 100] range."""
    engine = QualityScoringEngine(min_length=50, max_length=10000)

    # Perfect content — long enough, no issues
    good_content = "This is a well-written paragraph with sufficient length to pass quality checks. It contains meaningful content."
    score_good = engine.score(good_content)
    assert 0 <= score_good.score <= 100

    # Terrible content — too short, placeholder text
    bad_content = "Short"
    score_bad = engine.score(bad_content)
    assert 0 <= score_bad.score <= 100
    assert score_bad.score < score_good.score
    assert len(score_bad.flags) > 0

    # Content with placeholder text
    placeholder_content = "This is [INSERT HERE] some content that has placeholder text in it."
    score_placeholder = engine.score(placeholder_content)
    assert 0 <= score_placeholder.score <= 100
    assert any("placeholder" in f.lower() for f in score_placeholder.flags)

    # Test glossary checking
    glossary = [{"term": "Kubernetes", "definition": "Container orchestration"}]
    content_without_term = "This content talks about containers but misses the key term."
    score_no_glossary = engine.score(content_without_term, glossary=glossary)
    assert 0 <= score_no_glossary.score <= 100
    assert any("Kubernetes" in f for f in score_no_glossary.flags)


# ---------------------------------------------------------------------------
# Test: fallback router uses secondary on failure
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fallback_router_uses_secondary_on_failure() -> None:
    """Test that fallback router switches to secondary provider on primary failure."""
    primary = MockLLMProvider(name="primary", should_fail=True)
    secondary = MockLLMProvider(name="secondary", should_fail=False)

    config = CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=60.0,
        success_threshold=1,
    )
    router = FallbackRouter(primary=primary, secondary=secondary, config=config)

    # Initially should use primary (circuit closed)
    provider1 = await router.route_request()
    assert provider1.provider_name == "primary"

    # Record failures to trip the circuit breaker
    await router.record_failure()
    await router.record_failure()

    # Circuit should now be open, routing to secondary
    provider2 = await router.route_request()
    assert provider2.provider_name == "secondary"

    # Record success on secondary — should stay on secondary until recovery timeout
    await router.record_success()
    provider3 = await router.route_request()
    assert provider3.provider_name == "secondary"


# ---------------------------------------------------------------------------
# Test: fallback router recovers after timeout
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fallback_router_recovers_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that circuit breaker recovers after recovery timeout."""
    import time as time_module

    primary = MockLLMProvider(name="primary", should_fail=False)
    secondary = MockLLMProvider(name="secondary", should_fail=False)

    config = CircuitBreakerConfig(
        failure_threshold=1,
        recovery_timeout=5.0,
        success_threshold=1,
    )
    router = FallbackRouter(primary=primary, secondary=secondary, config=config)

    # Trip the circuit breaker
    await router.record_failure()
    provider = await router.route_request()
    assert provider.provider_name == "secondary"

    # Simulate time passing beyond recovery timeout
    fake_time = time_module.time() + 10.0
    monkeypatch.setattr("pulse.llm.fallback_router.time.time", lambda: fake_time)

    # Should transition to half-open and try primary again
    provider = await router.route_request()
    assert provider.provider_name == "primary"

    # Success should close the circuit
    await router.record_success()
    provider = await router.route_request()
    assert provider.provider_name == "primary"
