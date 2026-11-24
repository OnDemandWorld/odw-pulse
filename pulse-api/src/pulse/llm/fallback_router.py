"""Fallback router for LLM providers.

Implements circuit breaker pattern to automatically failover from
primary to secondary provider when the primary is unhealthy or failing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pulse.llm.base import LLMProvider


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, using primary
    OPEN = "open"  # Primary failing, using secondary
    HALF_OPEN = "half_open"  # Testing if primary recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before testing primary again
        success_threshold: Number of successful tests before closing circuit
    """

    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    success_threshold: int = 2


class FallbackRouter:
    """Routes requests between primary and secondary providers with circuit breaker.

    The router attempts to use the primary provider, but automatically falls
    back to the secondary provider when the primary is unhealthy or has
    exceeded the failure threshold.
    """

    def __init__(
        self,
        primary: LLMProvider,
        secondary: LLMProvider,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize the fallback router.

        Args:
            primary: The preferred provider to use
            secondary: The fallback provider to use when primary fails
            config: Optional circuit breaker configuration
        """
        self.primary = primary
        self.secondary = secondary
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        # In-flight probe requests admitted to the primary in HALF_OPEN
        # (audit finding #17).
        self._half_open_probes = 0

    @property
    def state(self) -> CircuitState:
        """Return the current circuit breaker state."""
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state."""
        if self._state != new_state:
            self._state = new_state
            # Reset counters on state transitions
            if new_state == CircuitState.CLOSED:
                self._failure_count = 0
                self._success_count = 0
            elif new_state == CircuitState.OPEN:
                self._success_count = 0
            elif new_state == CircuitState.HALF_OPEN:
                self._failure_count = 0
                self._half_open_probes = 0

    async def route_request(self, config: dict[str, Any] | None = None) -> LLMProvider:
        """Select the appropriate provider based on circuit state.

        Args:
            config: Optional request configuration (currently unused)

        Returns:
            The LLMProvider to use for this request
        """
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                return self.secondary
        if self._state == CircuitState.CLOSED:
            return self.primary
        # HALF_OPEN — audit finding #17: admit only a bounded number of
        # concurrent probes to the possibly-still-dead primary; everything
        # else keeps using the secondary until the probes conclude.
        if self._half_open_probes < max(1, self.config.success_threshold):
            self._half_open_probes += 1
            return self.primary
        return self.secondary

    def _is_primary(self, provider: str | None) -> bool:
        """Whether a recorded outcome belongs to the primary provider."""
        return provider is None or provider == self.primary.provider_name

    async def record_success(self, provider: str | None = None) -> None:
        """Record a successful request to update circuit state.

        Args:
            provider: Name of the provider that served the request. Only
                primary outcomes drive HALF_OPEN recovery; secondary
                successes while probing must not close the circuit.
        """
        if self._state == CircuitState.HALF_OPEN:
            if not self._is_primary(provider):
                return
            self._half_open_probes = max(0, self._half_open_probes - 1)
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    async def record_failure(self, provider: str | None = None) -> None:
        """Record a failed request to update circuit state.

        Args:
            provider: Name of the provider that failed. Failures recorded
                while OPEN (i.e. secondary failures) must NOT refresh the
                recovery timer, or a failing secondary keeps the circuit
                open forever (audit finding #16).
        """
        if self._state == CircuitState.HALF_OPEN:
            if not self._is_primary(provider):
                return
            self._half_open_probes = max(0, self._half_open_probes - 1)
            self._last_failure_time = time.time()
            # A failed probe re-opens the circuit
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            self._last_failure_time = time.time()
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        # OPEN: ignore — the recovery timer runs from the moment the
        # circuit opened, regardless of secondary failures.
