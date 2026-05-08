"""
Memory base — bütün bellek backend'lerinin uyacağı arayüz.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """Soyut bellek arayüzü."""

    @abstractmethod
    def add(self, item: dict[str, Any]) -> None: ...

    @abstractmethod
    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def clear(self) -> None: ...

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Varsayılan: son N kaydı döndür (override edilebilir)."""
        return self.get_recent(limit)
