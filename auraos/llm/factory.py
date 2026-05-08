"""
get_llm — provider/model string'inden uygun LLM örneği döndürür.

Format: "provider/model", örn: "anthropic/claude-sonnet-4-5".
Provider girilmezse "openai" varsayılır.
"""
from __future__ import annotations
import os

from auraos.llm.base import BaseLLM


def get_llm(model: str, **kwargs) -> BaseLLM:
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        provider, model_name = "openai", model

    provider = provider.lower()

    if provider == "openai":
        from auraos.llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model_name, **kwargs)

    if provider == "anthropic":
        from auraos.llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model_name, **kwargs)

    if provider in ("google", "gemini"):
        from auraos.llm.providers.gemini_provider import GoogleGeminiProvider
        return GoogleGeminiProvider(model=model_name, **kwargs)

    if provider == "ollama":
        from auraos.llm.providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=model_name, **kwargs)

    raise ValueError(f"Bilinmeyen provider: {provider}")
