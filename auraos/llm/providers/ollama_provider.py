"""Ollama (lokal LLM) provider."""
from __future__ import annotations
import os
from typing import Any, Optional

import httpx

from auraos.llm.base import BaseLLM, LLMResponse
from auraos.tools.schema import ToolSchema


class OllamaProvider(BaseLLM):
    def __init__(self, model: str, host: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": m["role"], "content": m.get("content") or ""}
                for m in messages
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self.host}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            tokens_used=data.get("eval_count", 0),
            raw=data,
        )
