"""
MCP (Model Context Protocol) Client — external MCP server'lara bağlantı.
"""
from __future__ import annotations
from typing import Any, Callable

from auraos.mcp.config import MCPServerConfig
from auraos.mcp.adapter import MCPToolCallable, build_mcp_tools


def _lazy_client():
    from auraos.mcp.client import MCPClient
    return MCPClient


def get_mcp_tools(*configs: MCPServerConfig) -> tuple[list[Callable], list[Any]]:
    """Birden fazla MCP server'a bağlan, tüm tool'ları döndür.

    Returns:
        (tools, clients) tuple'ı. Client'ları kapatmak çağıranın sorumluluğundadır.

    Kullanım:
        tools, clients = get_mcp_tools(
            MCPServerConfig(name="fs", transport="stdio", command="npx",
                          args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                          tool_prefix="fs_"),
        )
        agent = Agent(tools=[my_tool, *tools])
        # İşiniz bitince:
        for c in clients:
            c.disconnect()
    """
    MCPClient = _lazy_client()
    all_tools: list[Callable] = []
    clients: list[Any] = []
    for config in configs:
        client = MCPClient(config)
        client.connect()
        clients.append(client)
        all_tools.extend(build_mcp_tools(client))
    return all_tools, clients


__all__ = [
    "MCPServerConfig",
    "MCPToolCallable",
    "build_mcp_tools",
    "get_mcp_tools",
]
