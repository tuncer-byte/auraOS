"""Anthropic provider."""
from __future__ import annotations
import os
from typing import Any, Optional

from auraos.llm.base import BaseLLM, LLMResponse
from auraos.tools.schema import ToolSchema


class AnthropicProvider(BaseLLM):
    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic paketi yok: pip install anthropic")

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
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

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_msgs,
            "system": system.strip() or None,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = [t.to_anthropic() for t in tools]

        resp = self.client.messages.create(**{k: v for k, v in kwargs.items() if v is not None})

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

        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            tokens_used=(resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0,
            raw=resp,
        )
