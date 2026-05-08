"""
Embedding sağlayıcıları.

Bütün sağlayıcılar EmbeddingProvider arayüzünü uygular.
KnowledgeBase semantic search için bunlardan birini kullanır.

Backendler:
  - HashEmbedding   : harici bağımlılık yok, deterministik bag-of-words hash
  - OpenAIEmbedding : text-embedding-3-small (varsayılan)
  - GeminiEmbedding : text-embedding-004
  - SentenceTransformerEmbedding : local CPU
"""
from __future__ import annotations
import hashlib
import math
import os
import re
from abc import ABC, abstractmethod
from typing import Optional

from auraos.exceptions import LLMAuthError


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class EmbeddingProvider(ABC):
    dimensions: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class HashEmbedding(EmbeddingProvider):
    """
    Bağımlılık-sız fallback. Token hash + bucket. Semantic değil ama
    deterministik ve testler için güvenilir.
    """

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions
        self._tok = re.compile(r"\w+", re.UNICODE)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dimensions
            tokens = [m.group(0).lower() for m in self._tok.finditer(t)]
            for tok in tokens:
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                vec[h % self.dimensions] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            out.append(vec)
        return out


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMAuthError("OPENAI_API_KEY gerekli")
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai paketi yok: pip install openai")
        self.dimensions = 1536 if "small" in model else 3072

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class GeminiEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "text-embedding-004", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMAuthError("GOOGLE_API_KEY gerekli")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._genai = genai
        except ImportError:
            raise ImportError("google-generativeai paketi yok")
        self.dimensions = 768

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            resp = self._genai.embed_content(model=f"models/{self.model}", content=t)
            out.append(resp["embedding"])
        return out


class SentenceTransformerEmbedding(EmbeddingProvider):
    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            raise ImportError("sentence-transformers yüklü değil: pip install sentence-transformers")
        self._model = SentenceTransformer(model)
        self.dimensions = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.encode(texts, show_progress_bar=False)]


def get_embedding_provider(name: str = "hash", **kwargs) -> EmbeddingProvider:
    name = name.lower()
    if name == "hash":
        return HashEmbedding(**kwargs)
    if name == "openai":
        return OpenAIEmbedding(**kwargs)
    if name in ("gemini", "google"):
        return GeminiEmbedding(**kwargs)
    if name in ("sentence_transformer", "st", "local"):
        return SentenceTransformerEmbedding(**kwargs)
    raise ValueError(f"Bilinmeyen embedding provider: {name}")
