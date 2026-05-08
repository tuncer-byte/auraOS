"""
LLM Provider abstraction.

Bütün sağlayıcılar (OpenAI, Anthropic, Google, Ollama, Mock) aynı
arayüzü uygular: messages + tools alır, içerik + tool_calls döner.

API:
  - complete(...)  : sync, tek seferde tam yanıt
  - acomplete(...) : async, tek seferde tam yanıt
  - stream(...)    : sync generator, parça parça
  - astream(...)   : async generator, parça parça
"""
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator, Literal, Optional

from auraos.tools.schema import ToolSchema


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    raw: Any = None


@dataclass
class StreamChunk:
    """Streaming sırasında her bir parça."""
    type: Literal["text", "tool_call", "done", "error"]
    text: str = ""
    tool_call: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    raw: Any = None


class BaseLLM(ABC):
    """Tüm LLM sağlayıcılarının uygulaması gereken arayüz."""

    supports_streaming: bool = False
    supports_tools: bool = True

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.config = kwargs

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Sync: mesajları gönder, tam yanıtı döndür."""
        ...

    async def acomplete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Async: varsayılan olarak complete()'i thread'de çalıştırır."""
        return await asyncio.to_thread(
            self.complete, messages, tools, temperature, max_tokens
        )

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[StreamChunk]:
        """Sync streaming. Default: complete sonra tek chunk olarak döner."""
        try:
            resp = self.complete(messages, tools, temperature, max_tokens)
            if resp.content:
                yield StreamChunk(type="text", text=resp.content)
            for tc in resp.tool_calls:
                yield StreamChunk(type="tool_call", tool_call=tc)
            yield StreamChunk(type="done", raw=resp)
        except Exception as e:
            yield StreamChunk(type="error", error=str(e))

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Async streaming. Default: stream()'i thread'de iterate eder."""
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        def producer():
            try:
                for chunk in self.stream(messages, tools, temperature, max_tokens):
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop).result()

        task = asyncio.create_task(asyncio.to_thread(producer))
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                yield item
        finally:
            await task
