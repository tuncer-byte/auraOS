"""Anthropic provider — streaming + async + error classification."""
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


class AnthropicProvider(BaseLLM):
    supports_streaming = True

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        try:
            from anthropic import Anthropic, AsyncAnthropic
            self.client = Anthropic(api_key=self.api_key)
            self.async_client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic paketi yok: pip install anthropic")

    def _classify_error(self, e: Exception) -> Exception:
        msg = str(e).lower()
        if "authentication" in msg or "api key" in msg or "unauthorized" in msg:
            return LLMAuthError(str(e))
        if "rate" in msg or "429" in msg or "quota" in msg:
            return LLMRateLimitError(str(e))
        if "connection" in msg or "timeout" in msg or "network" in msg or "overloaded" in msg:
            return LLMConnectionError(str(e))
        return LLMResponseError(str(e))

    def _prepare_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        system = ""
        api_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                system += (m.get("content") or "") + "\n"
            elif m["role"] == "tool":
                api_msgs.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m.get("content", ""),
                    }],
                })
            else:
                api_msgs.append({"role": m["role"], "content": m.get("content") or ""})
        return system.strip(), api_msgs

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        system, api_msgs = self._prepare_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [t.to_anthropic() for t in tools]
        return kwargs

    def _parse_response(self, resp: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input or {},
                })

        inp = resp.usage.input_tokens if resp.usage else 0
        out = resp.usage.output_tokens if resp.usage else 0

        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            tokens_used=inp + out,
            input_tokens=inp,
            output_tokens=out,
            raw=resp,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            kwargs = self._build_kwargs(messages, tools, temperature, max_tokens)
            resp = self.client.messages.create(**kwargs)
            return self._parse_response(resp)
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
            resp = await self.async_client.messages.create(**kwargs)
            return self._parse_response(resp)
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
            current_tool: dict[str, Any] | None = None
            tool_args_json = ""

            with self.client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool = {"id": block.id, "name": block.name}
                            tool_args_json = ""
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamChunk(type="text", text=delta.text)
                        elif delta.type == "input_json_delta":
                            tool_args_json += delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool:
                            yield StreamChunk(type="tool_call", tool_call={
                                "id": current_tool["id"],
                                "name": current_tool["name"],
                                "arguments": json.loads(tool_args_json) if tool_args_json else {},
                            })
                            current_tool = None
                            tool_args_json = ""

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
            current_tool: dict[str, Any] | None = None
            tool_args_json = ""

            async with self.async_client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool = {"id": block.id, "name": block.name}
                            tool_args_json = ""
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamChunk(type="text", text=delta.text)
                        elif delta.type == "input_json_delta":
                            tool_args_json += delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool:
                            yield StreamChunk(type="tool_call", tool_call={
                                "id": current_tool["id"],
                                "name": current_tool["name"],
                                "arguments": json.loads(tool_args_json) if tool_args_json else {},
                            })
                            current_tool = None
                            tool_args_json = ""

            yield StreamChunk(type="done")
        except Exception as e:
            yield StreamChunk(type="error", error=str(e))
