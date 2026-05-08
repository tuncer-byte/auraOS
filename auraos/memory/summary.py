"""
SummaryMemory — uzun bağlamı LLM ile özetleyerek tutar.
"""
from __future__ import annotations
from typing import Any, Optional

from auraos.memory.base import Memory
from auraos.llm.base import BaseLLM


class SummaryMemory(Memory):
    def __init__(self, llm: BaseLLM, max_raw_items: int = 20):
        self.llm = llm
        self.max_raw_items = max_raw_items
        self._raw: list[dict[str, Any]] = []
        self._summary: str = ""

    def add(self, item: dict[str, Any]) -> None:
        self._raw.append(item)
        if len(self._raw) > self.max_raw_items:
            self._compact()

    def _compact(self) -> None:
        text = "\n".join(
            f"[{m.get('role')}] {m.get('content')}" for m in self._raw
        )
        prompt = (
            "Aşağıdaki konuşma geçmişini kısa ve bilgi-yoğun bir özet olarak yaz. "
            "Önemli kararları, sayısal veriyi ve niyetleri koru.\n\n"
            f"GEÇMİŞ:\n{text}\n\nÖZET:"
        )
        resp = self.llm.complete([{"role": "user", "content": prompt}])
        self._summary = (self._summary + "\n" + resp.content).strip()
        self._raw = []

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if self._summary:
            items.append({"role": "system", "content": f"Özet bağlam: {self._summary}"})
        items.extend(self._raw[-limit:])
        return items

    def clear(self) -> None:
        self._raw.clear()
        self._summary = ""
