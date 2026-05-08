"""Token + USD maliyet takibi.

LLM bütçesi, banka için anlık takibi gereken bir şey. Her completion sonrası
provider+model'e göre tarifeyi uygular, session bazında biriktirir.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass


# USD per 1k tokens. (referans: 2025-2026 yayınlanmış aralıklar; gerçek üretimde
# config'ten yönetilir.)
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    # input, output
    "gemini-2.5-flash": (0.000075, 0.0003),
    "gemini-2.5-pro": (0.00125, 0.005),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "claude-haiku-4-5": (0.0008, 0.004),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-opus-4-7": (0.015, 0.075),
}


@dataclass
class CostEntry:
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    calls: int = 0


class CostTracker:
    """Session ve global bazda token/USD biriktiren thread-safe sayaç."""

    def __init__(self, pricing: dict[str, tuple[float, float]] | None = None) -> None:
        self.pricing = dict(DEFAULT_PRICING)
        if pricing:
            self.pricing.update(pricing)
        self._sessions: dict[str, CostEntry] = defaultdict(CostEntry)
        self._models: dict[str, CostEntry] = defaultdict(CostEntry)
        self._global = CostEntry()
        self._lock = threading.Lock()

    def _normalize_model(self, model: str) -> str:
        m = model.lower()
        if "/" in m:
            m = m.split("/", 1)[1]
        return m

    def price_for(self, model: str) -> tuple[float, float]:
        m = self._normalize_model(model)
        if m in self.pricing:
            return self.pricing[m]
        for key, val in self.pricing.items():
            if m.startswith(key) or key.startswith(m):
                return val
        return (0.0, 0.0)

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        session_id: str | None = None,
    ) -> float:
        in_rate, out_rate = self.price_for(model)
        usd = (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate
        with self._lock:
            for entry in (self._global, self._models[self._normalize_model(model)]):
                entry.input_tokens += input_tokens
                entry.output_tokens += output_tokens
                entry.usd += usd
                entry.calls += 1
            if session_id:
                e = self._sessions[session_id]
                e.input_tokens += input_tokens
                e.output_tokens += output_tokens
                e.usd += usd
                e.calls += 1
        return usd

    def session(self, session_id: str) -> CostEntry:
        return self._sessions.get(session_id, CostEntry())

    def model(self, model: str) -> CostEntry:
        return self._models.get(self._normalize_model(model), CostEntry())

    def total(self) -> CostEntry:
        return self._global

    def snapshot(self) -> dict:
        return {
            "total": self._global.__dict__.copy(),
            "by_model": {k: v.__dict__.copy() for k, v in self._models.items()},
            "by_session": {k: v.__dict__.copy() for k, v in self._sessions.items()},
        }
