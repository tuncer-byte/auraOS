"""Integration tests for LLM providers — each skipped without its API key."""
import asyncio
import os
import pytest

from auraos.llm.base import LLMResponse, StreamChunk
from auraos.llm.factory import get_llm
from auraos.tools.schema import ToolSchema


def run_async(coro):
    return asyncio.run(coro)


WEATHER_TOOL = ToolSchema(
    name="get_weather",
    description="Get current weather for a city",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
        },
        "required": ["city"],
    },
)

# --- Skip markers ---

requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)

requires_anthropic = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

requires_gemini = pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="GEMINI_API_KEY/GOOGLE_API_KEY not set",
)

requires_groq = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set",
)

SIMPLE_MSG = [{"role": "user", "content": "Say hello in one word."}]
TOOL_MSG = [{"role": "user", "content": "What is the weather in Istanbul?"}]


# ========== OpenAI ==========

@requires_openai
class TestOpenAI:
    def _llm(self):
        return get_llm("openai/gpt-4o-mini")

    def test_complete(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_tokens(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0
        assert resp.tokens_used == resp.input_tokens + resp.output_tokens

    def test_tool_calling(self):
        resp = self._llm().complete(TOOL_MSG, tools=[WEATHER_TOOL], max_tokens=200)
        assert len(resp.tool_calls) > 0
        assert resp.tool_calls[0]["name"] == "get_weather"

    def test_stream(self):
        chunks = list(self._llm().stream(SIMPLE_MSG, max_tokens=50))
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"

    def test_acomplete(self):
        resp = run_async(self._llm().acomplete(SIMPLE_MSG, max_tokens=50))
        assert len(resp.content) > 0

    def test_astream(self):
        async def _run():
            chunks = []
            async for c in self._llm().astream(SIMPLE_MSG, max_tokens=50):
                chunks.append(c)
            return chunks
        chunks = run_async(_run())
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"


# ========== Anthropic ==========

@requires_anthropic
class TestAnthropic:
    def _llm(self):
        return get_llm("anthropic/claude-haiku-4-5")

    def test_complete(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_tokens(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0

    def test_tool_calling(self):
        resp = self._llm().complete(TOOL_MSG, tools=[WEATHER_TOOL], max_tokens=200)
        assert len(resp.tool_calls) > 0
        assert resp.tool_calls[0]["name"] == "get_weather"

    def test_stream(self):
        chunks = list(self._llm().stream(SIMPLE_MSG, max_tokens=50))
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"

    def test_acomplete(self):
        resp = run_async(self._llm().acomplete(SIMPLE_MSG, max_tokens=50))
        assert len(resp.content) > 0

    def test_astream(self):
        async def _run():
            chunks = []
            async for c in self._llm().astream(SIMPLE_MSG, max_tokens=50):
                chunks.append(c)
            return chunks
        chunks = run_async(_run())
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"


# ========== Gemini ==========

@requires_gemini
class TestGemini:
    def _llm(self):
        return get_llm("gemini/gemini-2.5-flash")

    def test_complete(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_tokens(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0

    def test_tool_calling(self):
        resp = self._llm().complete(TOOL_MSG, tools=[WEATHER_TOOL], max_tokens=200)
        assert len(resp.tool_calls) > 0
        assert resp.tool_calls[0]["name"] == "get_weather"

    def test_stream(self):
        chunks = list(self._llm().stream(SIMPLE_MSG, max_tokens=50))
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"

    def test_acomplete(self):
        resp = run_async(self._llm().acomplete(SIMPLE_MSG, max_tokens=50))
        assert len(resp.content) > 0

    def test_astream(self):
        async def _run():
            chunks = []
            async for c in self._llm().astream(SIMPLE_MSG, max_tokens=50):
                chunks.append(c)
            return chunks
        chunks = run_async(_run())
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"


# ========== Groq ==========

@requires_groq
class TestGroq:
    def _llm(self):
        return get_llm("groq/llama-3.3-70b-versatile")

    def test_complete(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert isinstance(resp, LLMResponse)
        assert len(resp.content) > 0

    def test_tokens(self):
        resp = self._llm().complete(SIMPLE_MSG, max_tokens=50)
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0

    def test_tool_calling(self):
        resp = self._llm().complete(TOOL_MSG, tools=[WEATHER_TOOL], max_tokens=200)
        assert len(resp.tool_calls) > 0
        assert resp.tool_calls[0]["name"] == "get_weather"

    def test_stream(self):
        chunks = list(self._llm().stream(SIMPLE_MSG, max_tokens=50))
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"

    def test_acomplete(self):
        resp = run_async(self._llm().acomplete(SIMPLE_MSG, max_tokens=50))
        assert len(resp.content) > 0

    def test_astream(self):
        async def _run():
            chunks = []
            async for c in self._llm().astream(SIMPLE_MSG, max_tokens=50):
                chunks.append(c)
            return chunks
        chunks = run_async(_run())
        types = [c.type for c in chunks]
        assert "text" in types
        assert types[-1] == "done"
