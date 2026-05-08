"""
Retry yardımcıları - exponential backoff + jitter.

Tenacity'siz hafif implementasyon. Sadece retry edilebilir hatalarda
yeniden dener (Connection, Timeout, RateLimit). Auth hataları ve
kullanıcı hatalarında derhal düşer.
"""
from __future__ import annotations
import asyncio
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Type

from auraos.exceptions import (
    AuraOSError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from auraos.utils.logger import get_logger

logger = get_logger(__name__)


DEFAULT_RETRYABLE: tuple[Type[BaseException], ...] = (
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    ConnectionError,
    TimeoutError,
)


def _compute_delay(
    attempt: int,
    base: float,
    cap: float,
    jitter: bool,
    explicit_retry_after: Optional[float],
) -> float:
    if explicit_retry_after is not None:
        return min(explicit_retry_after, cap)
    delay = min(cap, base * (2 ** (attempt - 1)))
    if jitter:
        delay = random.uniform(0.0, delay)
    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retry_on: tuple[Type[BaseException], ...] = DEFAULT_RETRYABLE,
):
    """Senkron fonksiyonlar için retry decorator."""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt >= max_attempts:
                        break
                    retry_after = getattr(e, "retry_after", None)
                    delay = _compute_delay(attempt, base_delay, max_delay, jitter, retry_after)
                    logger.warning(
                        f"{fn.__name__} attempt {attempt}/{max_attempts} failed: {e}; sleeping {delay:.2f}s"
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return deco


def aretry(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retry_on: tuple[Type[BaseException], ...] = DEFAULT_RETRYABLE,
):
    """Async fonksiyonlar için retry decorator."""

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt >= max_attempts:
                        break
                    retry_after = getattr(e, "retry_after", None)
                    delay = _compute_delay(attempt, base_delay, max_delay, jitter, retry_after)
                    logger.warning(
                        f"{fn.__name__} attempt {attempt}/{max_attempts} failed: {e}; sleeping {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return deco
