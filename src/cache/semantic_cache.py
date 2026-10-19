"""Exact and semantic caching to cut latency and cost."""

from __future__ import annotations

from typing import Any


class SemanticCache:
    def __init__(self, redis_url: str | None = None, ttl_seconds: int = 3600):
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._exact: dict[str, Any] = {}

    def get_exact(self, key: str) -> Any | None:
        return self._exact.get(key)

    def set_exact(self, key: str, value: Any) -> None:
        self._exact[key] = value

    def get_semantic(self, query: str, threshold: float = 0.92) -> Any | None:
        _ = (query, threshold)
        return None

    def set_semantic(self, query: str, value: Any) -> None:
        _ = (query, value)
