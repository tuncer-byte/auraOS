"""Google Gemini provider (basit sürüm)."""
from __future__ import annotations
import os
from typing import Any, Optional

from auraos.llm.base import BaseLLM, LLMResponse
from auraos.tools.schema import ToolSchema


class GoogleProvider(BaseLLM):
    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
        except ImportError:
            raise ImportError(
                "google-generativeai paketi yok: pip install google-generativeai"
            )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        prompt_parts = []
        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            prompt_parts.append(f"[{role}] {content}")
        prompt = "\n".join(prompt_parts)

        model = self._genai.GenerativeModel(self.model)
        resp = model.generate_content(prompt)
        return LLMResponse(content=resp.text or "", raw=resp)
