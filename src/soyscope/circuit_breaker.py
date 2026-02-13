"""Circuit breaker for fault tolerance."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker pattern implementation.

    Tracks failures for an API and temporarily disables it when too many
    failures occur in succession.
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    half_open_max_calls: int = 1

    _state: CircuitState = field(init=False, default=CircuitState.CLOSED)
    _failure_count: int = field(init=False, default=0)
    _success_count: int = field(init=False, default=0)
    _last_failure_time: float = field(init=False, default=0.0)
    _half_open_calls: int = field(init=False, default=0)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    @property
    def is_available(self) -> bool:
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def record_call(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1


class CircuitBreakerRegistry:
    """Registry of circuit breakers, one per API."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def register(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 60.0) -> None:
        self._breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def get(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name)
        return self._breakers[name]

    def is_available(self, name: str) -> bool:
        return self.get(name).is_available

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "state": cb.state.value,
                "failures": cb._failure_count,
                "available": cb.is_available,
            }
            for name, cb in self._breakers.items()
        }


# Global registry
circuit_breakers = CircuitBreakerRegistry()


def setup_circuit_breakers() -> CircuitBreakerRegistry:
    """Set up circuit breakers for all known APIs."""
    for name in ["exa", "openalex", "semantic_scholar", "crossref",
                 "pubmed", "tavily", "core", "unpaywall", "claude",
                 "osti", "patentsview", "sbir", "agris", "lens", "usda_ers"]:
        circuit_breakers.register(name, failure_threshold=5, recovery_timeout=60.0)
    return circuit_breakers
