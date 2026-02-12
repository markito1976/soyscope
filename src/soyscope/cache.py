"""diskcache-based search caching."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


class SearchCache:
    """Persistent disk cache for search results.

    Uses diskcache to store API responses keyed by (api_name, query, params).
    Default TTL is 7 days.
    """

    def __init__(self, cache_dir: str | Path, default_ttl: int = 7 * 24 * 3600) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(self.cache_dir), size_limit=2 * 1024 ** 3)  # 2GB
        self.default_ttl = default_ttl

    def _make_key(self, api_name: str, query: str, params: dict[str, Any] | None = None) -> str:
        raw = json.dumps({"api": api_name, "query": query, "params": params or {}}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, api_name: str, query: str, params: dict[str, Any] | None = None) -> Any | None:
        key = self._make_key(api_name, query, params)
        return self._cache.get(key)

    def set(self, api_name: str, query: str, results: Any,
            params: dict[str, Any] | None = None, ttl: int | None = None) -> None:
        key = self._make_key(api_name, query, params)
        self._cache.set(key, results, expire=ttl or self.default_ttl)

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._cache),
            "volume": self._cache.volume(),
            "directory": str(self.cache_dir),
        }

    def close(self) -> None:
        self._cache.close()
