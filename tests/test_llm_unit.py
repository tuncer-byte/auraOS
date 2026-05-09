"""Unit tests for LLM provider abstractions — no API key needed."""
import pytest
from auraos.llm.base import LLMResponse, StreamChunk
from auraos.tools.schema import ToolSchema
from auraos.llm.factory import get_llm
from auraos.observability.cost import CostTracker


class TestLLMResponse:
    def test_default_fields(self):
        r = LLMResponse()
        assert r.content == ""
        assert r.tool_calls == []
        assert r.tokens_used == 0
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.raw is None

    def test_with_tokens(self):
        r = LLMResponse(
            content="hello",
            tokens_used=100,
            input_tokens=60,
            output_tokens=40,
        )
        assert r.tokens_used == 100
        assert r.input_tokens == 60
        assert r.output_tokens == 40

    def test_backward_compat(self):
        r = LLMResponse(content="hi", tokens_used=50)
        assert r.tokens_used == 50
        assert r.input_tokens == 0
        assert r.output_tokens == 0


class TestStreamChunk:
    def test_text_chunk(self):
        c = StreamChunk(type="text", text="hello")
        assert c.type == "text"
        assert c.text == "hello"

    def test_tool_call_chunk(self):
        tc = {"id": "1", "name": "get_weather", "arguments": {"city": "Istanbul"}}
        c = StreamChunk(type="tool_call", tool_call=tc)
        assert c.type == "tool_call"
        assert c.tool_call["name"] == "get_weather"

    def test_done_chunk(self):
        c = StreamChunk(type="done")
        assert c.type == "done"

    def test_error_chunk(self):
        c = StreamChunk(type="error", error="timeout")
        assert c.error == "timeout"


class TestToolSchemaFormats:
    @pytest.fixture
    def schema(self):
        return ToolSchema(
            name="get_weather",
            description="Get current weather",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
        )

    def test_to_openai(self, schema):
        result = schema.to_openai()
        assert result["type"] == "function"
        assert result["function"]["name"] == "get_weather"
        assert result["function"]["description"] == "Get current weather"
        assert "properties" in result["function"]["parameters"]

    def test_to_anthropic(self, schema):
        result = schema.to_anthropic()
        assert result["name"] == "get_weather"
        assert result["description"] == "Get current weather"
        assert "input_schema" in result
        assert result["input_schema"]["type"] == "object"

    def test_to_gemini(self, schema):
        result = schema.to_gemini()
        assert result["name"] == "get_weather"
        assert result["description"] == "Get current weather"
        assert result["parameters"]["type"] == "object"

    def test_to_groq_equals_openai(self, schema):
        assert schema.to_groq() == schema.to_openai()


class TestFactory:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Bilinmeyen provider"):
            get_llm("unknown_provider/some-model")


class TestCostTrackerNewModels:
    def test_groq_model_pricing(self):
        tracker = CostTracker()
        price = tracker.price_for("llama-3.3-70b-versatile")
        assert price[0] > 0
        assert price[1] > 0

    def test_claude_opus_46_pricing(self):
        tracker = CostTracker()
        price = tracker.price_for("claude-opus-4-6")
        assert price[0] > 0

    def test_gpt41_pricing(self):
        tracker = CostTracker()
        price = tracker.price_for("gpt-4.1")
        assert price[0] > 0
