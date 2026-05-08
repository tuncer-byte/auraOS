"""Tests for auraOS v0.3 - Tool Architecture."""
import asyncio
import os
import pytest

from auraos.tools.decorator import tool, streaming_tool
from auraos.tools.registry import ToolRegistry
from auraos.tools.context import ToolExecutionContext, create_context
from auraos.tools.subagent import create_sub_agent_tool, create_agent_router
from auraos.exceptions import ToolError


def run_async(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


def _has_llm_key() -> bool:
    return bool(
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GOOGLE_API_KEY") or
        os.getenv("ANTHROPIC_API_KEY")
    )


requires_llm = pytest.mark.skipif(
    not _has_llm_key(),
    reason="No LLM API key available; test skipped.",
)


class TestToolComposition:
    """Tests for tool composition via ToolExecutionContext."""

    def test_context_creation(self):
        registry = ToolRegistry()
        ctx = create_context(registry, session_id="test-session")

        assert ctx.registry is registry
        assert ctx.session_id == "test-session"
        assert ctx.depth == 0

    def test_context_depth_tracking(self):
        registry = ToolRegistry()

        @tool
        def outer():
            return "outer"

        @tool
        def inner():
            return "inner"

        registry.register(outer)
        registry.register(inner)

        ctx = create_context(registry)
        assert ctx.depth == 0

    def test_context_service_registration(self):
        registry = ToolRegistry()

        class MyService:
            def do_something(self):
                return "done"

        service = MyService()
        registry.set_service(MyService, service)

        ctx = create_context(registry, services={MyService: service})
        assert ctx.has_service(MyService)
        assert ctx.get_service(MyService) is service

    def test_context_service_not_found(self):
        registry = ToolRegistry()
        ctx = create_context(registry)

        class UnregisteredService:
            pass

        with pytest.raises(ToolError) as exc:
            ctx.get_service(UnregisteredService)
        assert "not registered" in str(exc.value)


class TestComposableTool:
    """Tests for composable tools."""

    def test_composable_tool_decorator(self):
        @tool(composable=True)
        def composable_func(value: int, ctx=None) -> dict:
            """A composable tool."""
            return {"value": value * 2}

        assert composable_func.__auraos_composable__ is True

    def test_composable_removes_ctx_from_schema(self):
        @tool(composable=True)
        def composable_func(value: int, ctx=None) -> dict:
            """A composable tool."""
            return {"value": value}

        schema = composable_func.__auraos_schema__
        props = schema.parameters.get("properties", {})
        assert "ctx" not in props

    def test_registry_injects_context(self):
        registry = ToolRegistry()

        @tool(composable=True)
        def composable_tool(value: int, ctx=None) -> dict:
            if ctx is not None:
                return {"value": value, "has_ctx": True, "depth": ctx.depth}
            return {"value": value, "has_ctx": False}

        registry.register(composable_tool)

        ctx = create_context(registry)
        result = registry.invoke("composable_tool", {"value": 42}, context=ctx)

        assert result["has_ctx"] is True
        assert result["depth"] == 0


class TestStreamingTool:
    """Tests for streaming tools."""

    def test_streaming_tool_decorator(self):
        @streaming_tool
        async def stream_data(query: str):
            """Streams data."""
            for i in range(3):
                yield {"chunk": i}

        assert stream_data.__auraos_streaming__ is True


class TestSubAgentTool:
    """Tests for sub-agent tool factory."""

    @requires_llm
    def test_create_sub_agent_tool_metadata(self):
        from auraos import Agent

        agent = Agent(name="TestAgent")
        tool_func = create_sub_agent_tool(agent, name="run_test")

        assert tool_func.__auraos_tool__ is True
        assert tool_func.__auraos_sub_agent__ is True
        assert tool_func.__auraos_sub_agent_name__ == "TestAgent"

    @requires_llm
    def test_create_agent_router_metadata(self):
        from auraos import Agent

        agents = {
            "kyc": Agent(name="KYC"),
            "aml": Agent(name="AML"),
        }
        router = create_agent_router(agents, name="dispatch")

        assert router.__auraos_tool__ is True
        assert router.__auraos_agent_router__ is True
        assert set(router.__auraos_routed_agents__) == {"kyc", "aml"}


class TestParallelToolExecution:
    """Tests for parallel tool execution in Agent."""

    @requires_llm
    def test_agent_parallel_tools_config(self):
        from auraos import Agent

        agent = Agent(name="ParallelAgent", parallel_tools=True, max_tool_concurrency=3)
        assert agent.parallel_tools is True
        assert agent.max_tool_concurrency == 3

    @requires_llm
    def test_agent_default_sequential(self):
        from auraos import Agent

        agent = Agent(name="SeqAgent")
        assert agent.parallel_tools is False
        assert agent.max_tool_concurrency == 5


class TestToolRegistryServices:
    """Tests for service registration in ToolRegistry."""

    def test_set_and_get_service(self):
        registry = ToolRegistry()

        class DatabaseService:
            def query(self):
                return []

        db = DatabaseService()
        registry.set_service(DatabaseService, db)

        assert registry.get_service(DatabaseService) is db

    def test_get_unregistered_service(self):
        registry = ToolRegistry()

        class UnknownService:
            pass

        result = registry.get_service(UnknownService)
        assert result is None


class TestComplianceTools:
    """Tests for compliance tools."""

    def test_comprehensive_aml_check(self):
        from auraos.fintech.compliance_tools import comprehensive_aml_check

        result = run_async(comprehensive_aml_check(
            customer_name="Normal Customer",
            tc_kimlik="12345678901",
            birth_date="1990-01-15",
        ))

        assert "risk_level" in result
        assert result["risk_level"] in ["low", "medium", "high"]
        assert "credit_score" in result
        assert "recommendation" in result
