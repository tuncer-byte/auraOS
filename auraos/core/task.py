"""
Task — bir agent'ın yürüteceği iş birimi.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import uuid4


@dataclass
class Task:
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[str] = None
    max_iterations: int = 25
    require_human_approval: bool = False
    task_id: str = field(default_factory=lambda: str(uuid4())[:8])
    tools: Optional[list[Callable]] = None
    response_format: Optional[type] = None
    images: Optional[list[str]] = None
    system_prompt: Optional[str] = None

    def to_prompt(self) -> str:
        parts = [f"GÖREV: {self.description}"]
        if self.context:
            parts.append(f"CONTEXT: {self.context}")
        if self.expected_output:
            parts.append(f"BEKLENEN ÇIKTI: {self.expected_output}")
        if self.images:
            parts.append(f"[{len(self.images)} görsel ekli]")
        if self.response_format is not None:
            try:
                schema = self.response_format.model_json_schema()
                parts.append(
                    f"YANIT FORMATI: Yanıtını aşağıdaki JSON şemasına uygun ver.\n{schema}"
                )
            except (AttributeError, TypeError):
                pass
        return "\n".join(parts)
