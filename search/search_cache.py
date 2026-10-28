"""
JARVIS Search Hot Cache.
Dual-layer cache: Redis with transparent in-memory TTL fallback.
Ensures sub-5ms repeated query latency.
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional


class SearchCache:
    def __init__(self, redis_url: Optional[str] = None, default_ttl_sec: int = 3600):
        self.default_ttl_sec = default_ttl_sec
        self.redis_client = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

        if redis_url:
            try:
                import redis
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)
                self.redis_client.ping()
            except Exception:
                self.redis_client = None

    @staticmethod
    def _key(query: str, mode: str) -> str:
        clean_q = query.strip().lower()
        h = hashlib.sha256(f"{clean_q}::{mode}".encode()).hexdigest()
        return f"jarvis:search:{h}"

    def get(self, query: str, mode: str = "hybrid") -> Optional[Dict[str, Any]]:
        """Retrieve cached search response. Returns None on cache miss."""
        key = self._key(query, mode)

        # 1. Try Redis if available
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    self.hits += 1
                    data = json.loads(cached)
                    data["cache_hit"] = True
                    return data
            except Exception:
                pass

        # 2. Try In-Memory Fallback
        entry = self._memory_cache.get(key)
        if entry:
            if time.time() < entry["expires_at"]:
                self.hits += 1
                data = dict(entry["data"])
                data["cache_hit"] = True
                return data
            else:
                del self._memory_cache[key]

        self.misses += 1
        return None

    def set(
        self,
        query: str,
        mode: str,
        data: Dict[str, Any],
        ttl_sec: Optional[int] = None,
    ) -> None:
        """Cache search result payload with TTL."""
        key = self._key(query, mode)
        ttl = ttl_sec or self.default_ttl_sec

        # 1. Store in Redis if available
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(data))
            except Exception:
                pass

        # 2. Always store in memory fallback
        self._memory_cache[key] = {
            "data": data,
            "expires_at": time.time() + ttl,
        }

    def clear(self) -> int:
        """Clear all search cache entries."""
        count = len(self._memory_cache)
        self._memory_cache.clear()

        if self.redis_client:
            try:
                keys = self.redis_client.keys("jarvis:search:*")
                if keys:
                    count += len(keys)
                    self.redis_client.delete(*keys)
            except Exception:
                pass

        return count

    def stats(self) -> Dict[str, Any]:
        """Return cache hit-rate and capacity statistics."""
        total = self.hits + self.misses
        hit_ratio = round((self.hits / total * 100), 1) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio_percent": hit_ratio,
            "in_memory_entries": len(self._memory_cache),
            "redis_connected": bool(self.redis_client),
        }
