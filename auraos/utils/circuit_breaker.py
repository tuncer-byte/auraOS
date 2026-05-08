"""Circuit breaker - başarısız bağımlılıkları geçici izole eder.

State machine: closed → open (eşik aşıldı) → half_open (cooldown bitti, deneme
trafiği). Banking ortamında LLM/3rd party servis arızalandığında milisaniye
içinde patlayıp normalize sürecini başlatmak gerekiyor.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum

from ..exceptions import AuraOSError


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(AuraOSError):
    """Devre açık - çağrı reddedildi."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_seconds: float = 30.0
    half_open_max_calls: int = 1
    state: CircuitState = CircuitState.CLOSED
    _failures: int = 0
    _opened_at: float = 0.0
    _half_open_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _transition_if_recovered(self) -> None:
        if self.state == CircuitState.OPEN and (time.time() - self._opened_at) >= self.recovery_seconds:
            self.state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def allow(self) -> bool:
        with self._lock:
            self._transition_if_recovered()
            if self.state == CircuitState.OPEN:
                return False
            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return False
                self._half_open_calls += 1
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self.state = CircuitState.CLOSED
                self._half_open_calls = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self.state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self._opened_at = time.time()

    def call(self, fn, *args, **kwargs):
        if not self.allow():
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    async def acall(self, fn, *args, **kwargs):
        if not self.allow():
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = await fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failures,
            "opened_at": self._opened_at,
        }
