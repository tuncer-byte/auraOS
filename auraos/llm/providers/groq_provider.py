"""Groq provider — OpenAI-uyumlu API, streaming + async + tools."""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Iterator, Optional

from auraos.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMResponseError,
)
from auraos.llm.base import BaseLLM, LLMResponse, StreamChunk
from auraos.tools.schema import ToolSchema


class GroqProvider(BaseLLM):
    supports_streaming = True

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        try:
            from groq import Groq, AsyncGroq
            self.client = Groq(api_key=self.api_key)
            self.async_client = AsyncGroq(api_key=self.api_key)
        except ImportError:
            raise ImportError("groq paketi yok: pip install groq")

    def _classify_error(self, e: Exception) -> Exception:
        msg = str(e).lower()
        if "authentication" in msg or "api key" in msg or "unauthorized" in msg:
            return LLMAuthError(str(e))
        if "rate" in msg or "429" in msg or "quota" in msg:
            return LLMRateLimitError(str(e))
        if "connection" in msg or "timeout" in msg or "network" in msg:
            return LLMConnectionError(str(e))
        return LLMResponseError(str(e))

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [t.to_groq() for t in tools]
            kwargs["tool_choice"] = "auto"
        return kwargs

    def _parse_tool_calls(self, msg: Any) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
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
            kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
            resp = self.client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message

            inp = resp.usage.prompt_tokens if resp.usage else 0
            out = resp.usage.completion_tokens if resp.usage else 0

            return LLMResponse(
                content=msg.content or "",
                tool_calls=self._parse_tool_calls(msg),
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
            kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
            resp = await self.async_client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message

            inp = resp.usage.prompt_tokens if resp.usage else 0
            out = resp.usage.completion_tokens if resp.usage else 0

            return LLMResponse(
                content=msg.content or "",
                tool_calls=self._parse_tool_calls(msg),
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
            kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
            kwargs["stream"] = True
            response = self.client.chat.completions.create(**kwargs)

            pending_tool_calls: dict[int, dict[str, Any]] = {}

            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    yield StreamChunk(type="text", text=delta.content)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                                "arguments_str": "",
                            }
                        if tc_delta.function and tc_delta.function.arguments:
                            pending_tool_calls[idx]["arguments_str"] += tc_delta.function.arguments
                        if tc_delta.id:
                            pending_tool_calls[idx]["id"] = tc_delta.id

                finish = chunk.choices[0].finish_reason if chunk.choices else None
                if finish == "tool_calls":
                    for tc_data in pending_tool_calls.values():
                        yield StreamChunk(type="tool_call", tool_call={
                            "id": tc_data["id"],
                            "name": tc_data["name"],
                            "arguments": json.loads(tc_data["arguments_str"] or "{}"),
                        })
                    pending_tool_calls.clear()

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
            kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
            kwargs["stream"] = True
            response = await self.async_client.chat.completions.create(**kwargs)

            pending_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    yield StreamChunk(type="text", text=delta.content)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                                "arguments_str": "",
                            }
                        if tc_delta.function and tc_delta.function.arguments:
                            pending_tool_calls[idx]["arguments_str"] += tc_delta.function.arguments
                        if tc_delta.id:
                            pending_tool_calls[idx]["id"] = tc_delta.id

                finish = chunk.choices[0].finish_reason if chunk.choices else None
                if finish == "tool_calls":
                    for tc_data in pending_tool_calls.values():
                        yield StreamChunk(type="tool_call", tool_call={
                            "id": tc_data["id"],
                            "name": tc_data["name"],
                            "arguments": json.loads(tc_data["arguments_str"] or "{}"),
                        })
                    pending_tool_calls.clear()

            yield StreamChunk(type="done")
        except Exception as e:
            yield StreamChunk(type="error", error=str(e))
