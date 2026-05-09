"""
MCPClient — MCP sunucusuna bağlanıp tool discovery ve invocation yapar.

Her MCPClient kendi daemon thread'inde bir event loop çalıştırır.
MCP session bu loop'ta yaşar. Tüm MCP işlemleri
asyncio.run_coroutine_threadsafe ile bu loop'a submit edilir.
"""
from __future__ import annotations
import asyncio
import concurrent.futures
import contextlib
import json
import threading
from typing import Any, Callable, Optional

from auraos.exceptions import MCPConnectionError, MCPToolCallError
from auraos.mcp.config import MCPServerConfig


def _require_mcp() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        raise ImportError(
            "MCP SDK gerekli. Kurun: pip install 'auraos[mcp]' veya pip install mcp"
        )


class MCPClient:
    """Tek bir MCP server'a bağlanıp tool'larını sunar."""

    def __init__(self, config: MCPServerConfig):
        _require_mcp()
        self._config = config
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Any = None
        self._exit_stack: Optional[contextlib.AsyncExitStack] = None
        self._tool_cache: Optional[list[dict[str, Any]]] = None
        self._connected = False

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ---- Lifecycle ----

    def _start_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name=f"mcp-{self._config.name}",
        )
        self._thread.start()

    def _submit(self, coro: Any) -> Any:
        if self._loop is None or not self._loop.is_running():
            raise MCPConnectionError(self._config.name, "MCP loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=self._config.timeout)
        except concurrent.futures.TimeoutError:
            raise MCPToolCallError(
                "mcp", f"Timeout after {self._config.timeout}s"
            )
        except (MCPConnectionError, MCPToolCallError):
            raise
        except Exception as e:
            raise MCPToolCallError("mcp", str(e)) from e

    async def _connect_impl(self) -> None:
        from mcp.client.session import ClientSession

        self._exit_stack = contextlib.AsyncExitStack()
        await self._exit_stack.__aenter__()

        if self._config.transport == "stdio":
            from mcp.client.stdio import StdioServerParameters, stdio_client

            params = StdioServerParameters(
                command=self._config.command,
                args=self._config.args,
                env=self._config.env,
            )
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
        elif self._config.transport == "sse":
            from mcp.client.sse import sse_client

            read, write = await self._exit_stack.enter_async_context(
                sse_client(
                    url=self._config.url,
                    headers=self._config.headers or {},
                )
            )
        else:
            raise MCPConnectionError(
                self._config.name,
                f"Desteklenmeyen transport: {self._config.transport}",
            )

        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()

    def connect(self) -> None:
        if self._connected:
            return
        self._start_loop()
        try:
            self._submit(self._connect_impl())
            self._connected = True
        except Exception:
            self._stop_loop()
            raise

    async def aconnect(self) -> None:
        self.connect()

    async def _disconnect_impl(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None

    def _stop_loop(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            self._submit(self._disconnect_impl())
        except Exception:
            pass
        self._stop_loop()
        self._connected = False
        self._tool_cache = None

    async def adisconnect(self) -> None:
        self.disconnect()

    def _ensure_connected(self) -> None:
        if not self._connected:
            self.connect()

    # ---- Context managers ----

    def __enter__(self) -> "MCPClient":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.disconnect()

    async def __aenter__(self) -> "MCPClient":
        self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.disconnect()

    # ---- Tool discovery ----

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_connected()
        if self._tool_cache is not None:
            return self._tool_cache
        result = self._submit(self._session.list_tools())
        self._tool_cache = [
            {
                "name": t.name,
                "description": getattr(t, "description", "") or "",
                "inputSchema": getattr(t, "inputSchema", {}) or {},
            }
            for t in result.tools
        ]
        return self._tool_cache

    def refresh_tools(self) -> list[dict[str, Any]]:
        self._tool_cache = None
        return self.list_tools()

    # ---- Tool invocation ----

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self._ensure_connected()
        result = self._submit(self._session.call_tool(name, arguments=arguments))
        return self._convert_result(name, result)

    def _convert_result(self, tool_name: str, result: Any) -> Any:
        if getattr(result, "isError", False):
            texts = []
            for c in getattr(result, "content", []):
                if hasattr(c, "text"):
                    texts.append(c.text)
            raise MCPToolCallError(
                tool_name, "; ".join(texts) if texts else "MCP tool error"
            )

        parts: list[Any] = []
        for content in getattr(result, "content", []):
            if hasattr(content, "text"):
                parts.append(content.text)
            elif hasattr(content, "data"):
                parts.append(
                    {
                        "type": "image",
                        "mimeType": getattr(content, "mimeType", ""),
                        "data": content.data,
                    }
                )
            else:
                parts.append(str(content))

        if len(parts) == 0:
            return None
        if len(parts) == 1:
            val = parts[0]
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    return val
            return val
        return parts

    # ---- Convenience ----

    def get_tools(self) -> list[Callable]:
        from auraos.mcp.adapter import build_mcp_tools

        return build_mcp_tools(self)

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"MCPClient(name={self._config.name!r}, {status})"
