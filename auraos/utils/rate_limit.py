"""
Token bucket rate limiter.

Provider başına ayrı bucket. Hem RPM (requests per minute) hem TPM
(tokens per minute) sınırı destekler. async ve sync varyantlar.
"""
from __future__ import annotations
import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from auraos.exceptions import RateLimitExceededError


@dataclass
class TokenBucket:
    """Klasik token bucket. capacity birim, refill_per_sec hızında dolar."""

    capacity: float
    refill_per_sec: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    _lock: threading.Lock = field(init=False, repr=False)
    _alock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
        self._alock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last_refill = now

    def _time_to_available(self, amount: float) -> float:
        deficit = amount - self.tokens
        if deficit <= 0:
            return 0.0
        return deficit / self.refill_per_sec

    def try_acquire(self, amount: float = 1.0) -> bool:
        """Tek seferlik dene; yetersizse False döner, beklemez."""
        with self._lock:
            self._refill()
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

    def acquire(self, amount: float = 1.0, timeout: Optional[float] = None) -> None:
        """Token bulunana kadar bekle. timeout aşılırsa hata."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
                wait = self._time_to_available(amount)
            if deadline is not None and time.monotonic() + wait > deadline:
                raise RateLimitExceededError("token_bucket", retry_after=wait)
            time.sleep(min(wait, 0.5))

    async def aacquire(self, amount: float = 1.0, timeout: Optional[float] = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            async with self._alock:
                self._refill()
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
                wait = self._time_to_available(amount)
            if deadline is not None and time.monotonic() + wait > deadline:
                raise RateLimitExceededError("token_bucket", retry_after=wait)
            await asyncio.sleep(min(wait, 0.5))


class RateLimiter:
    """
    Çoklu scope (provider/user/global) destekleyen wrapper.

    Örnek:
        rl = RateLimiter()
        rl.add_bucket("openai_rpm", capacity=60, refill_per_sec=1.0)
        rl.acquire("openai_rpm")
    """

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def add_bucket(self, scope: str, capacity: float, refill_per_sec: float) -> None:
        self._buckets[scope] = TokenBucket(capacity=capacity, refill_per_sec=refill_per_sec)

    def acquire(self, scope: str, amount: float = 1.0, timeout: Optional[float] = None) -> None:
        bucket = self._buckets.get(scope)
        if bucket is None:
            return
        bucket.acquire(amount, timeout)

    async def aacquire(self, scope: str, amount: float = 1.0, timeout: Optional[float] = None) -> None:
        bucket = self._buckets.get(scope)
        if bucket is None:
            return
        await bucket.aacquire(amount, timeout)


_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter
