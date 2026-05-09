"""
KnowledgeBase — RAG için belge ekleme + vektör arama.

Backend olarak in-memory (TF-IDF/keyword) veya Chroma seçilebilir.
Embedding sağlayıcı: sentence-transformers veya basit hash.
"""
from __future__ import annotations
import math
import re
from collections import Counter
from typing import Any, Optional

from auraos.knowledge.document import Document
from auraos.knowledge.chunker import chunk_text
from auraos.knowledge.splitters import TextSplitter, FixedSplitter


class KnowledgeBase:
    """
    Belgeleri ekleyip semantic/keyword araması yapan basit RAG katmanı.

    Args:
        backend: "memory" (varsayılan, TF-IDF) veya "chroma".
        embedder: Opsiyonel embedding fonksiyonu.
    """

    def __init__(
        self,
        backend: str = "memory",
        embedder: Optional[Any] = None,
        collection: str = "auraos_kb",
        splitter: Optional[TextSplitter] = None,
    ):
        self.backend = backend
        self.embedder = embedder
        self.collection = collection
        self.splitter = splitter
        self._docs: list[Document] = []
        self._chroma = None

        if backend == "chroma":
            try:
                import chromadb
                self._chroma = chromadb.Client().create_collection(
                    name=collection, get_or_create=True
                )
            except ImportError:
                raise ImportError("chromadb yok: pip install chromadb")

    def add(
        self,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
        chunk_size: int = 500,
        splitter: Optional[TextSplitter] = None,
    ) -> list[str]:
        """Bir metni chunk'layıp ekler, eklenen doc_id'leri döner."""
        s = splitter or self.splitter
        if s:
            chunks = s.split(text)
        else:
            chunks = chunk_text(text, chunk_size=chunk_size)
        ids: list[str] = []
        for chunk in chunks:
            doc = Document(content=chunk, metadata=metadata or {})
            if self.embedder:
                doc.embedding = self.embedder(chunk)
            self._docs.append(doc)
            ids.append(doc.doc_id)
            if self._chroma:
                self._chroma.add(
                    ids=[doc.doc_id],
                    documents=[chunk],
                    metadatas=[metadata or {}],
                )
        return ids

    def add_file(
        self,
        path: str,
        metadata: Optional[dict[str, Any]] = None,
        chunk_size: int = 500,
        splitter: Optional[TextSplitter] = None,
        loader: Optional[Any] = None,
    ) -> list[str]:
        """Dosyayı yükle, chunk'la, ekle."""
        from auraos.knowledge.loaders import get_loader, DocumentLoader
        if loader is None:
            loader = get_loader(path)
        docs = loader.load(path)
        ids: list[str] = []
        for doc in docs:
            merged_meta = {**(doc.metadata or {}), **(metadata or {})}
            ids.extend(self.add(doc.content, metadata=merged_meta, chunk_size=chunk_size, splitter=splitter))
        return ids

    def search(self, query: str, top_k: int = 3) -> str:
        """Sorguya en yakın belgeleri bul ve birleştirilmiş metin döndür."""
        results = self.search_docs(query, top_k=top_k)
        return "\n\n---\n\n".join(d.content for d in results)

    def search_docs(self, query: str, top_k: int = 3) -> list[Document]:
        if self._chroma:
            res = self._chroma.query(query_texts=[query], n_results=top_k)
            return [
                Document(content=c, metadata=m or {}, doc_id=i)
                for c, m, i in zip(
                    res.get("documents", [[]])[0],
                    res.get("metadatas", [[]])[0],
                    res.get("ids", [[]])[0],
                )
            ]
        return self._tfidf_search(query, top_k)

    def _tfidf_search(self, query: str, top_k: int) -> list[Document]:
        if not self._docs:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        df: Counter = Counter()
        doc_tokens: list[list[str]] = []
        for d in self._docs:
            toks = _tokenize(d.content)
            doc_tokens.append(toks)
            for t in set(toks):
                df[t] += 1

        n = len(self._docs)
        scores: list[tuple[float, Document]] = []
        for d, toks in zip(self._docs, doc_tokens):
            if not toks:
                continue
            tf = Counter(toks)
            score = 0.0
            for q in q_tokens:
                if q not in tf:
                    continue
                idf = math.log((n + 1) / (df[q] + 1)) + 1
                score += (tf[q] / len(toks)) * idf
            if score > 0:
                scores.append((score, d))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scores[:top_k]]

    def __len__(self) -> int:
        return len(self._docs)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())
