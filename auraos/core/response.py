"""
AgentResponse — agent'ın görev sonunda dönen standart çıktısı.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: Any
    duration_ms: float = 0.0


@dataclass
class AgentResponse:
    """Agent çalışmasının yapılandırılmış sonucu."""
    output: str
    success: bool = True
    error: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    tokens_used: int = 0
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.output
