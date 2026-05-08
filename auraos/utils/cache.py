"""
In-memory + opsiyonel Redis cache.

Hash'lenmiş key ile LLM çağrıları, embeddings ve tool sonuçları
saklanabilir. TTL destekli, async-safe.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


def make_cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, default=str, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class _Entry:
    value: Any
    expires_at: float  # 0 = ebedi


@dataclass
class InMemoryCache:
    max_size: int = 1024
    default_ttl: float = 3600.0
    _store: dict[str, _Entry] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _evict_if_needed(self) -> None:
        if len(self._store) <= self.max_size:
            return
        # En yakın süresi dolmuş veya en eski expires_at'e sahip olanı at
        oldest = min(self._store.items(), key=lambda kv: kv[1].expires_at or float("inf"))
        self._store.pop(oldest[0], None)

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at and entry.expires_at < time.time():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl if ttl > 0 else 0.0
        self._store[key] = _Entry(value=value, expires_at=expires_at)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def get_or_compute(self, key: str, compute: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value, ttl)
        return value

    async def aget_or_compute(
        self,
        key: str,
        compute: Callable[[], Awaitable[Any]],
        ttl: Optional[float] = None,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = await compute()
            self.set(key, value, ttl)
            return value


class RedisCache:
    """
    Opsiyonel Redis backend. redis-py kuruluysa kullanılır.
    Yoksa InMemoryCache fallback.
    """

    def __init__(self, url: str = "redis://localhost:6379/0", default_ttl: float = 3600.0, prefix: str = "auraos:"):
        self.default_ttl = default_ttl
        self.prefix = prefix
        try:
            import redis  # type: ignore
            self._client = redis.Redis.from_url(url, decode_responses=True)
            self._client.ping()
            self._available = True
        except Exception:
            self._available = False
            self._fallback = InMemoryCache(default_ttl=default_ttl)

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return self._fallback.get(key)
        raw = self._client.get(self._k(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if not self._available:
            return self._fallback.set(key, value, ttl)
        ttl = ttl if ttl is not None else self.default_ttl
        payload = json.dumps(value, default=str)
        if ttl > 0:
            self._client.setex(self._k(key), int(ttl), payload)
        else:
            self._client.set(self._k(key), payload)

    def delete(self, key: str) -> None:
        if not self._available:
            return self._fallback.delete(key)
        self._client.delete(self._k(key))


_default_cache: Optional[InMemoryCache] = None


def get_default_cache() -> InMemoryCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = InMemoryCache()
    return _default_cache
