"""Idempotency key store.

Kritik finansal araç çağrılarında (ör. para transferi) aynı isteğin iki kez
işlenmemesi için. İlk çağrı sonucu cache'lenir, aynı key ile ikinci çağrı saved
sonucu döner. TTL: ürünleştirmede 24h normaldir.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any


def make_idempotency_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass
class _Slot:
    value: Any
    expires_at: float


class IdempotencyStore:
    def __init__(self, default_ttl: float = 24 * 3600.0) -> None:
        self.default_ttl = default_ttl
        self._data: dict[str, _Slot] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[bool, Any]:
        with self._lock:
            slot = self._data.get(key)
            if not slot:
                return False, None
            if slot.expires_at < time.time():
                self._data.pop(key, None)
                return False, None
            return True, slot.value

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._data[key] = _Slot(value=value, expires_at=time.time() + (ttl or self.default_ttl))

    def remember(self, key: str, fn, ttl: float | None = None):
        hit, val = self.get(key)
        if hit:
            return val
        result = fn()
        self.put(key, result, ttl=ttl)
        return result
