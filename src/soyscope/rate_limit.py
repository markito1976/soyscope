"""Token bucket rate limiters per API."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    Allows `rate` requests per second with a burst capacity of `burst`.
    """
    rate: float
    burst: int = 0
    _tokens: float = field(init=False, default=0.0)
    _last_refill: float = field(init=False, default=0.0)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        if self.burst <= 0:
            self.burst = max(1, int(self.rate))
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate wait time for next token
                wait = (1.0 - self._tokens) / self.rate
                await asyncio.sleep(wait)

    def try_acquire(self) -> bool:
        """Try to acquire a token without waiting. Returns True if successful."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class RateLimiterRegistry:
    """Registry of rate limiters, one per API."""

    def __init__(self) -> None:
        self._limiters: dict[str, TokenBucket] = {}

    def register(self, name: str, rate: float, burst: int = 0) -> None:
        self._limiters[name] = TokenBucket(rate=rate, burst=burst)

    def get(self, name: str) -> TokenBucket:
        if name not in self._limiters:
            # Default: 1 QPS
            self._limiters[name] = TokenBucket(rate=1.0, burst=1)
        return self._limiters[name]

    async def acquire(self, name: str) -> None:
        await self.get(name).acquire()


# Global registry
rate_limiters = RateLimiterRegistry()


def setup_rate_limiters() -> RateLimiterRegistry:
    """Set up rate limiters for all known APIs."""
    rate_limiters.register("exa", rate=5.0, burst=5)
    rate_limiters.register("openalex", rate=10.0, burst=10)
    rate_limiters.register("semantic_scholar", rate=1.0, burst=1)
    rate_limiters.register("crossref", rate=50.0, burst=50)
    rate_limiters.register("pubmed", rate=10.0, burst=10)
    rate_limiters.register("tavily", rate=5.0, burst=5)
    rate_limiters.register("core", rate=5.0, burst=5)
    rate_limiters.register("unpaywall", rate=10.0, burst=10)
    rate_limiters.register("claude", rate=5.0, burst=5)
    # Tier 1 sources
    rate_limiters.register("osti", rate=1.0, burst=2)
    rate_limiters.register("patentsview", rate=0.75, burst=2)  # 45/min
    rate_limiters.register("sbir", rate=1.0, burst=2)
    rate_limiters.register("agris", rate=1.0, burst=2)
    rate_limiters.register("lens", rate=0.83, burst=2)  # 50/min
    rate_limiters.register("usda_ers", rate=1.0, burst=2)
    return rate_limiters
