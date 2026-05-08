"""
Google Gemini provider - Tool calling + streaming destekli.
"""
from __future__ import annotations
import asyncio
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
from auraos.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleGeminiProvider(BaseLLM):
    """Google Gemini API provider with function calling + streaming."""

    supports_streaming = True

    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise LLMAuthError("GOOGLE_API_KEY veya GEMINI_API_KEY environment variable gerekli")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
        except ImportError:
            raise ImportError("google-generativeai paketi yok: pip install google-generativeai")

    def _convert_tools(self, tools: list[ToolSchema]) -> list[dict]:
        decls = [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in tools
        ]
        return [{"function_declarations": decls}] if decls else []

    def _build_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[Any, str]:
        gemini_history: list[dict[str, Any]] = []
        system_instruction = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "") or ""
            if role == "system":
                system_instruction += content + "\n"
            elif role == "user":
                gemini_history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_history.append({"role": "model", "parts": [content]})
            elif role == "tool":
                gemini_history.append({"role": "user", "parts": [f"Tool sonucu: {content}"]})

        model = self._genai.GenerativeModel(
            self.model,
            system_instruction=system_instruction.strip() or None,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        chat = model.start_chat(history=gemini_history[:-1] if len(gemini_history) > 1 else [])
        last = gemini_history[-1]["parts"][0] if gemini_history else ""
        return chat, last

    def _classify_error(self, e: Exception) -> Exception:
        msg = str(e).lower()
        if "api key" in msg or "unauthorized" in msg or "permission" in msg:
            return LLMAuthError(str(e))
        if "rate" in msg or "quota" in msg or "429" in msg:
            return LLMRateLimitError(str(e))
        if "connection" in msg or "network" in msg or "timeout" in msg:
            return LLMConnectionError(str(e))
        return LLMResponseError(str(e))

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            chat, last = self._build_chat(messages, temperature, max_tokens)
            gemini_tools = self._convert_tools(tools) if tools else None
            response = chat.send_message(last, tools=gemini_tools) if gemini_tools else chat.send_message(last)

            tool_calls: list[dict[str, Any]] = []
            text_content = ""
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                        fc = part.function_call
                        tool_calls.append({
                            "id": fc.name,
                            "name": fc.name,
                            "arguments": dict(fc.args) if fc.args else {},
                        })
                    elif hasattr(part, "text") and part.text:
                        text_content += part.text

            tokens = (
                response.usage_metadata.total_token_count
                if hasattr(response, "usage_metadata") and response.usage_metadata
                else 0
            )
            return LLMResponse(content=text_content, tool_calls=tool_calls, tokens_used=tokens, raw=response)
        except Exception as e:
            logger.error(f"Gemini complete failed: {e}", exc_info=True)
            raise self._classify_error(e)

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[StreamChunk]:
        try:
            chat, last = self._build_chat(messages, temperature, max_tokens)
            gemini_tools = self._convert_tools(tools) if tools else None
            response = chat.send_message(
                last,
                tools=gemini_tools,
                stream=True,
            ) if gemini_tools else chat.send_message(last, stream=True)

            tool_emitted = False
            for chunk in response:
                if not chunk.candidates:
                    continue
                for candidate in chunk.candidates:
                    if not candidate.content or not candidate.content.parts:
                        continue
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                            fc = part.function_call
                            yield StreamChunk(type="tool_call", tool_call={
                                "id": fc.name,
                                "name": fc.name,
                                "arguments": dict(fc.args) if fc.args else {},
                            })
                            tool_emitted = True
                        elif hasattr(part, "text") and part.text:
                            yield StreamChunk(type="text", text=part.text)
            yield StreamChunk(type="done")
        except Exception as e:
            logger.error(f"Gemini stream failed: {e}", exc_info=True)
            yield StreamChunk(type="error", error=str(e))

    async def astream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
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
