"""Belge modeli."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Document:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str = field(default_factory=lambda: str(uuid4()))
    embedding: list[float] | None = None
