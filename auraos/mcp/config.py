"""
MCP Server konfigürasyonu.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class MCPServerConfig:
    name: str
    transport: Literal["stdio", "sse"]
    command: Optional[str] = None
    args: list[str] = field(default_factory=list)
    env: Optional[dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    tool_prefix: Optional[str] = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.transport == "stdio" and not self.command:
            raise ValueError(
                f"MCPServerConfig '{self.name}': stdio transport requires 'command'"
            )
        if self.transport == "sse" and not self.url:
            raise ValueError(
                f"MCPServerConfig '{self.name}': sse transport requires 'url'"
            )
