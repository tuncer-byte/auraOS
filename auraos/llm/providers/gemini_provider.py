"""Google Gemini provider — new google-genai SDK, streaming + async + tools."""
from __future__ import annotations

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
    """Google Gemini API provider — google-genai SDK."""

    supports_streaming = True

    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise LLMAuthError("GOOGLE_API_KEY veya GEMINI_API_KEY environment variable gerekli")

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self._genai = genai
        except ImportError:
            raise ImportError("google-genai paketi yok: pip install google-genai")

    def _classify_error(self, e: Exception) -> Exception:
        msg = str(e).lower()
        if "api key" in msg or "unauthorized" in msg or "permission" in msg:
            return LLMAuthError(str(e))
        if "rate" in msg or "quota" in msg or "429" in msg:
            return LLMRateLimitError(str(e))
        if "connection" in msg or "network" in msg or "timeout" in msg:
            return LLMConnectionError(str(e))
        return LLMResponseError(str(e))

    def _build_contents_and_config(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]],
        temperature: float,
        max_tokens: int,
    ) -> tuple[list[Any], Any]:
        from google.genai import types

        system_instruction = ""
        contents: list[Any] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "") or ""

            if role == "system":
                system_instruction += content + "\n"
            elif role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=content)],
                ))
            elif role == "assistant":
                parts = []
                if content:
                    parts.append(types.Part.from_text(text=content))
                tc_list = msg.get("tool_calls", [])
                for tc in tc_list:
                    parts.append(types.Part.from_function_call(
                        name=tc["name"],
                        args=tc.get("arguments", {}),
                    ))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                tool_name = msg.get("name", msg.get("tool_call_id", "tool"))
                tool_content = msg.get("content", "")
                try:
                    import json
                    result_data = json.loads(tool_content) if isinstance(tool_content, str) else tool_content
                except (json.JSONDecodeError, TypeError):
                    result_data = {"result": tool_content}
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=tool_name,
                        response=result_data,
                    )],
                ))

        gemini_tools = None
        if tools:
            decls = [t.to_gemini() for t in tools]
            gemini_tools = [types.Tool(function_declarations=decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction.strip() or None,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=gemini_tools,
        )

        return contents, config

    def _parse_response(self, response: Any) -> LLMResponse:
        tool_calls: list[dict[str, Any]] = []
        text_content = ""

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                    fc = part.function_call
                    tool_calls.append({
                        "id": getattr(fc, "id", fc.name) or fc.name,
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    })
                elif hasattr(part, "text") and part.text:
                    text_content += part.text

        inp = 0
        out = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            inp = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            tokens_used=inp + out,
            input_tokens=inp,
            output_tokens=out,
            raw=response,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            contents, config = self._build_contents_and_config(messages, tools, temperature, max_tokens)
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Gemini complete failed: {e}", exc_info=True)
            raise self._classify_error(e)

    async def acomplete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            contents, config = self._build_contents_and_config(messages, tools, temperature, max_tokens)
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Gemini acomplete failed: {e}", exc_info=True)
            raise self._classify_error(e)

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[StreamChunk]:
        try:
            contents, config = self._build_contents_and_config(messages, tools, temperature, max_tokens)
            response = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )

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
                                "id": getattr(fc, "id", fc.name) or fc.name,
                                "name": fc.name,
                                "arguments": dict(fc.args) if fc.args else {},
                            })
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
        try:
            contents, config = self._build_contents_and_config(messages, tools, temperature, max_tokens)
            response = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )

            async for chunk in response:
                if not chunk.candidates:
                    continue
                for candidate in chunk.candidates:
                    if not candidate.content or not candidate.content.parts:
                        continue
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                            fc = part.function_call
                            yield StreamChunk(type="tool_call", tool_call={
                                "id": getattr(fc, "id", fc.name) or fc.name,
                                "name": fc.name,
                                "arguments": dict(fc.args) if fc.args else {},
                            })
                        elif hasattr(part, "text") and part.text:
                            yield StreamChunk(type="text", text=part.text)
            yield StreamChunk(type="done")
        except Exception as e:
            logger.error(f"Gemini astream failed: {e}", exc_info=True)
            yield StreamChunk(type="error", error=str(e))
