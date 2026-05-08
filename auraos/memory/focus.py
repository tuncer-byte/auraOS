"""
FocusMemory — agent'ın aktif görev bağlamı / scratch-pad'i.
Sadece o anki göreve dair "odak" notları tutar; görev biter bitmez sıfırlanır.
"""
from __future__ import annotations
from typing import Any

from auraos.memory.base import Memory


class FocusMemory(Memory):
    def __init__(self, max_items: int = 50):
        self._items: list[dict[str, Any]] = []
        self.max_items = max_items

    def add(self, item: dict[str, Any]) -> None:
        self._items.append(item)
        if len(self._items) > self.max_items:
            self._items = self._items[-self.max_items:]

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._items[-limit:]

    def clear(self) -> None:
        self._items.clear()

    def reset_for_new_task(self) -> None:
        """Yeni göreve geçildiğinde tüm odak verisini sil."""
        self.clear()
