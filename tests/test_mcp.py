"""
MCP modül testleri — config, adapter, validator uyumluluğu.

Gerçek MCP server gerektirmeyen unit testler.
"""
import inspect
import pytest

from auraos.mcp.config import MCPServerConfig
from auraos.mcp.adapter import MCPToolCallable, build_mcp_tools
from auraos.tools.schema import ToolSchema
from auraos.tools.validator import validate_tool_arguments
from auraos.exceptions import MCPError, MCPConnectionError, MCPToolCallError


# ──────────────────────────────────────────────
# MCPServerConfig
# ──────────────────────────────────────────────


class TestMCPServerConfig:
    def test_stdio_valid(self):
        cfg = MCPServerConfig(
            name="fs",
            transport="stdio",
            command="npx",
            args=["-y", "@mcp/server-filesystem", "/tmp"],
        )
        assert cfg.name == "fs"
        assert cfg.transport == "stdio"
        assert cfg.command == "npx"

    def test_stdio_missing_command(self):
        with pytest.raises(ValueError, match="stdio.*requires.*command"):
            MCPServerConfig(name="bad", transport="stdio")

    def test_sse_valid(self):
        cfg = MCPServerConfig(
            name="remote",
            transport="sse",
            url="http://localhost:8080/sse",
            headers={"Authorization": "Bearer tok"},
        )
        assert cfg.url == "http://localhost:8080/sse"
        assert cfg.headers == {"Authorization": "Bearer tok"}

    def test_sse_missing_url(self):
        with pytest.raises(ValueError, match="sse.*requires.*url"):
            MCPServerConfig(name="bad", transport="sse")

    def test_tool_prefix(self):
        cfg = MCPServerConfig(
            name="fs",
            transport="stdio",
            command="npx",
            tool_prefix="fs_",
        )
        assert cfg.tool_prefix == "fs_"

    def test_default_timeout(self):
        cfg = MCPServerConfig(name="x", transport="stdio", command="echo")
        assert cfg.timeout == 30.0

    def test_custom_env(self):
        cfg = MCPServerConfig(
            name="x",
            transport="stdio",
            command="echo",
            env={"TOKEN": "abc"},
        )
        assert cfg.env == {"TOKEN": "abc"}


# ──────────────────────────────────────────────
# MCPToolCallable
# ──────────────────────────────────────────────


class _FakeClient:
    """call_tool dönen minimal client stub."""

    def __init__(self):
        self.config = MCPServerConfig(name="test", transport="stdio", command="echo")
        self.last_call = None

    def call_tool(self, name, arguments):
        self.last_call = (name, arguments)
        return f"result-{name}"


class TestMCPToolCallable:
    def _make(self):
        client = _FakeClient()
        schema = ToolSchema(
            name="fs_read",
            description="Read a file",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        tc = MCPToolCallable(
            client=client,
            mcp_tool_name="read",
            schema=schema,
            server_name="test-server",
        )
        return tc, client

    def test_auraos_tool_flag(self):
        tc, _ = self._make()
        assert tc.__auraos_tool__ is True

    def test_schema_attached(self):
        tc, _ = self._make()
        assert tc.__auraos_schema__.name == "fs_read"
        assert tc.__auraos_schema__.description == "Read a file"

    def test_name_and_doc(self):
        tc, _ = self._make()
        assert tc.__name__ == "fs_read"
        assert tc.__doc__ == "Read a file"

    def test_call_delegates(self):
        tc, client = self._make()
        result = tc(path="/tmp/a.txt")
        assert client.last_call == ("read", {"path": "/tmp/a.txt"})
        assert result == "result-read"

    def test_mcp_server_attr(self):
        tc, _ = self._make()
        assert tc.__auraos_mcp_server__ == "test-server"
        assert tc.__auraos_mcp_original_name__ == "read"

    def test_approval_defaults_false(self):
        tc, _ = self._make()
        assert tc.__auraos_requires_approval__ is False

    def test_repr(self):
        tc, _ = self._make()
        r = repr(tc)
        assert "fs_read" in r
        assert "test-server" in r

    def test_not_coroutinefunction(self):
        tc, _ = self._make()
        assert not inspect.iscoroutinefunction(tc)


# ──────────────────────────────────────────────
# build_mcp_tools
# ──────────────────────────────────────────────


class _FakeDiscoveryClient:
    def __init__(self, tools, prefix=""):
        self._tools = tools
        self.config = MCPServerConfig(
            name="disc", transport="stdio", command="echo", tool_prefix=prefix or None
        )

    def list_tools(self):
        return self._tools


class TestBuildMCPTools:
    def test_basic_discovery(self):
        raw = [
            {"name": "list_files", "description": "List files", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "read_file", "description": "Read file"},
        ]
        client = _FakeDiscoveryClient(raw)
        tools = build_mcp_tools(client)
        assert len(tools) == 2
        assert tools[0].__name__ == "list_files"
        assert tools[1].__name__ == "read_file"

    def test_prefix_applied(self):
        raw = [{"name": "list_files", "description": "List"}]
        client = _FakeDiscoveryClient(raw, prefix="fs_")
        tools = build_mcp_tools(client)
        assert tools[0].__name__ == "fs_list_files"
        assert tools[0].__auraos_mcp_original_name__ == "list_files"

    def test_empty_tools(self):
        client = _FakeDiscoveryClient([])
        tools = build_mcp_tools(client)
        assert tools == []


# ──────────────────────────────────────────────
# Validator VAR_KEYWORD passthrough
# ──────────────────────────────────────────────


class TestValidatorKwargsPassthrough:
    def test_kwargs_function_passes_all_args(self):
        def mcp_tool(**kwargs):
            pass

        args = {"path": "/tmp/a.txt", "encoding": "utf-8", "extra": 42}
        result = validate_tool_arguments(mcp_tool, "test_tool", args)
        assert result == {"path": "/tmp/a.txt", "encoding": "utf-8", "extra": 42}

    def test_normal_function_strips_unknown(self):
        def my_func(name: str, age: int = 0):
            pass

        args = {"name": "test", "age": 25, "unknown_field": "xyz"}
        result = validate_tool_arguments(my_func, "test_tool", args)
        assert "unknown_field" not in result
        assert result["name"] == "test"

    def test_mcp_callable_passthrough(self):
        client = _FakeClient()
        schema = ToolSchema(name="t", description="d", parameters={})
        tc = MCPToolCallable(client=client, mcp_tool_name="t", schema=schema, server_name="s")
        args = {"a": 1, "b": "two", "c": [3]}
        result = validate_tool_arguments(tc, "t", args)
        assert result == {"a": 1, "b": "two", "c": [3]}


# ──────────────────────────────────────────────
# MCP Exception hierarchy
# ──────────────────────────────────────────────


class TestMCPExceptions:
    def test_hierarchy(self):
        assert issubclass(MCPError, Exception)
        assert issubclass(MCPConnectionError, MCPError)
        assert issubclass(MCPToolCallError, MCPError)

    def test_connection_error_attrs(self):
        e = MCPConnectionError("myserver", "refused")
        assert e.server_name == "myserver"
        assert "MCP:myserver" in str(e)

    def test_tool_call_error_attrs(self):
        e = MCPToolCallError("read_file", "not found")
        assert e.tool_name == "read_file"
        assert "MCP tool:read_file" in str(e)

    def test_to_dict(self):
        e = MCPConnectionError("s", "msg")
        d = e.to_dict()
        assert d["error"] == "MCPConnectionError"
        assert "msg" in d["message"]
