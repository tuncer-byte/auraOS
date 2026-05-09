"""Ollama provider — resmi ollama paketi, streaming + async + tools."""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Iterator, Optional

from auraos.exceptions import (
    LLMConnectionError,
    LLMResponseError,
)
from auraos.llm.base import BaseLLM, LLMResponse, StreamChunk
from auraos.tools.schema import ToolSchema


class OllamaProvider(BaseLLM):
    supports_streaming = True

    def __init__(self, model: str, host: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        try:
            import ollama as _ollama
            self._ollama = _ollama
        except ImportError:
            raise ImportError("ollama paketi yok: pip install ollama")

    def _classify_error(self, e: Exception) -> Exception:
        msg = str(e).lower()
        if "connection" in msg or "refused" in msg or "timeout" in msg or "unreachable" in msg:
            return LLMConnectionError(str(e))
        return LLMResponseError(str(e))

    def _format_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted = []
        for m in messages:
            formatted.append({"role": m["role"], "content": m.get("content") or ""})
        return formatted

    def _build_tools(self, tools: Optional[list[ToolSchema]]) -> list[dict] | None:
        if not tools:
            return None
        return [t.to_openai() for t in tools]

    def _extract_tokens(self, data: Any) -> tuple[int, int]:
        if isinstance(data, dict):
            inp = data.get("prompt_eval_count", 0) or 0
            out = data.get("eval_count", 0) or 0
        else:
            inp = getattr(data, "prompt_eval_count", 0) or 0
            out = getattr(data, "eval_count", 0) or 0
        return inp, out

    def _extract_tool_calls(self, msg: Any) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        raw_calls = None
        if isinstance(msg, dict):
            raw_calls = msg.get("tool_calls")
        else:
            raw_calls = getattr(msg, "tool_calls", None)

        if raw_calls:
            for tc in raw_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    tool_calls.append({
                        "id": func.get("name", ""),
                        "name": func.get("name", ""),
                        "arguments": func.get("arguments", {}),
                    })
                else:
                    func = getattr(tc, "function", None)
                    if func:
                        tool_calls.append({
                            "id": getattr(func, "name", ""),
                            "name": getattr(func, "name", ""),
                            "arguments": getattr(func, "arguments", {}),
                        })
        return tool_calls

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": self._format_messages(messages),
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            ollama_tools = self._build_tools(tools)
            if ollama_tools:
                kwargs["tools"] = ollama_tools

            client = self._ollama.Client(host=self.host)
            resp = client.chat(**kwargs)

            msg = resp.message if hasattr(resp, "message") else resp.get("message", {})
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            inp, out = self._extract_tokens(resp)

            return LLMResponse(
                content=content or "",
                tool_calls=self._extract_tool_calls(msg),
                tokens_used=inp + out,
                input_tokens=inp,
                output_tokens=out,
                raw=resp,
            )
        except Exception as e:
            raise self._classify_error(e)

    async def acomplete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": self._format_messages(messages),
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            ollama_tools = self._build_tools(tools)
            if ollama_tools:
                kwargs["tools"] = ollama_tools

            client = self._ollama.AsyncClient(host=self.host)
            resp = await client.chat(**kwargs)

            msg = resp.message if hasattr(resp, "message") else resp.get("message", {})
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            inp, out = self._extract_tokens(resp)

            return LLMResponse(
                content=content or "",
                tool_calls=self._extract_tool_calls(msg),
                tokens_used=inp + out,
                input_tokens=inp,
                output_tokens=out,
                raw=resp,
            )
        except Exception as e:
            raise self._classify_error(e)

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[StreamChunk]:
        try:
            client = self._ollama.Client(host=self.host)
            stream = client.chat(
                model=self.model,
                messages=self._format_messages(messages),
                options={"temperature": temperature, "num_predict": max_tokens},
                stream=True,
            )

            for chunk in stream:
                msg = chunk.message if hasattr(chunk, "message") else chunk.get("message", {})
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                if content:
                    yield StreamChunk(type="text", text=content)

            yield StreamChunk(type="done")
        except Exception as e:
            yield StreamChunk(type="error", error=str(e))

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        try:
            client = self._ollama.AsyncClient(host=self.host)
            stream = await client.chat(
                model=self.model,
                messages=self._format_messages(messages),
                options={"temperature": temperature, "num_predict": max_tokens},
                stream=True,
            )

            async for chunk in stream:
                msg = chunk.message if hasattr(chunk, "message") else chunk.get("message", {})
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                if content:
                    yield StreamChunk(type="text", text=content)

            yield StreamChunk(type="done")
        except Exception as e:
            yield StreamChunk(type="error", error=str(e))
