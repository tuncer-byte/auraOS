"""
Task — bir agent'ın yürüteceği iş birimi.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4


@dataclass
class Task:
    """
    Agent'a verilen tek bir görev.

    Args:
        description: Görevin doğal dil tanımı.
        context: Göreve eşlik eden ek veri (dosya yolu, parametre vs.).
        expected_output: Beklenen çıktı formatı (opsiyonel).
        max_iterations: Otonom agent için maksimum adım sayısı.
        require_human_approval: Tamamlanmadan önce insan onayı gereksin mi.
    """
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[str] = None
    max_iterations: int = 25
    require_human_approval: bool = False
    task_id: str = field(default_factory=lambda: str(uuid4())[:8])

    def to_prompt(self) -> str:
        parts = [f"GÖREV: {self.description}"]
        if self.context:
            parts.append(f"CONTEXT: {self.context}")
        if self.expected_output:
            parts.append(f"BEKLENEN ÇIKTI: {self.expected_output}")
        return "\n".join(parts)
