"""
MCP Tool Adapter — MCP tool'larını AuraOS ToolRegistry'ye uyumlu callable'lara çevirir.
"""
from __future__ import annotations
from typing import Any, Callable

from auraos.tools.schema import ToolSchema


class MCPToolCallable:
    """MCP tool'u saran, ToolRegistry ile uyumlu sync callable.

    __auraos_tool__ = True olduğu için registry is_tool() check'ini geçer
    ve @tool decorator yeniden uygulanmaz. __call__ sync'tir — MCPClient'ın
    background loop'una submit eder.
    """

    def __init__(
        self,
        client: Any,
        mcp_tool_name: str,
        schema: ToolSchema,
        server_name: str,
    ):
        self._client = client
        self._mcp_name = mcp_tool_name

        self.__name__ = schema.name
        self.__qualname__ = schema.name
        self.__doc__ = schema.description
        self.__auraos_tool__ = True
        self.__auraos_schema__ = schema
        self.__auraos_requires_approval__ = False
        self.__auraos_required_roles__: frozenset[str] = frozenset()
        self.__auraos_idempotent__ = False
        self.__auraos_composable__ = False
        self.__auraos_streaming__ = False
        self.__auraos_mcp_server__ = server_name
        self.__auraos_mcp_original_name__ = mcp_tool_name

    def __call__(self, **kwargs: Any) -> Any:
        return self._client.call_tool(self._mcp_name, kwargs)

    def __repr__(self) -> str:
        return (
            f"MCPToolCallable({self.__name__!r}, "
            f"server={self.__auraos_mcp_server__!r})"
        )


def build_mcp_tools(client: Any) -> list[Callable]:
    """MCP server'daki tool'ları keşfedip AuraOS-uyumlu callable listesi döndürür."""
    raw_tools = client.list_tools()
    prefix = client.config.tool_prefix or ""
    result: list[Callable] = []

    for t in raw_tools:
        tool_name = f"{prefix}{t['name']}" if prefix else t["name"]
        schema = ToolSchema(
            name=tool_name,
            description=t.get("description") or tool_name,
            parameters=t.get("inputSchema", {"type": "object", "properties": {}}),
        )
        callable_ = MCPToolCallable(
            client=client,
            mcp_tool_name=t["name"],
            schema=schema,
            server_name=client.config.name,
        )
        result.append(callable_)

    return result
