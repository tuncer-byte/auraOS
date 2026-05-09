"""
Text Splitters — yapılandırılabilir metin bölme stratejileri.

Sınıflar:
  - RecursiveSplitter: paragraf → cümle → kelime sınırlarından böler
  - MarkdownSplitter: başlık (#, ##, ###) sınırlarını kullanır
  - SentenceSplitter: cümle bazlı bölme (Türkçe desteği)
  - FixedSplitter: sabit karakter sayısı (chunk_text wrapper)
"""
from __future__ import annotations
import re
from abc import ABC, abstractmethod


class TextSplitter(ABC):
    @abstractmethod
    def split(self, text: str) -> list[str]:
        ...


class FixedSplitter(TextSplitter):
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        if self.chunk_size <= 0:
            return [text]
        chunks: list[str] = []
        i = 0
        while i < len(text):
            chunks.append(text[i : i + self.chunk_size])
            i += self.chunk_size - self.overlap
            if i < 0:
                break
        return [c for c in chunks if c.strip()]


class RecursiveSplitter(TextSplitter):
    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = separators or ["\n\n", "\n", ". ", " "]

    def split(self, text: str) -> list[str]:
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        if not separators:
            return self._fixed_split(text)

        sep = separators[0]
        remaining_seps = separators[1:]
        parts = text.split(sep)

        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > self.chunk_size:
                    chunks.extend(self._split_recursive(part, remaining_seps))
                    current = ""
                else:
                    current = part

        if current and current.strip():
            chunks.append(current)

        if self.overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks)

        return [c for c in chunks if c.strip()]

    def _fixed_split(self, text: str) -> list[str]:
        return FixedSplitter(self.chunk_size, self.overlap).split(text)

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-self.overlap:]
            result.append(prev_tail + chunks[i])
        return result


class MarkdownSplitter(TextSplitter):
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def split(self, text: str) -> list[str]:
        sections = re.split(r"(?m)^(#{1,6}\s+.+)$", text)
        chunks: list[str] = []
        current = ""

        for section in sections:
            if not section.strip():
                continue
            candidate = current + "\n" + section if current else section
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(section) > self.chunk_size:
                    chunks.extend(
                        FixedSplitter(self.chunk_size).split(section)
                    )
                    current = ""
                else:
                    current = section

        if current.strip():
            chunks.append(current.strip())

        return chunks


class SentenceSplitter(TextSplitter):
    def __init__(self, max_sentences: int = 10, overlap_sentences: int = 2):
        self.max_sentences = max_sentences
        self.overlap_sentences = overlap_sentences

    def split(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?…])\s+", text)
        sentences = [s for s in sentences if s.strip()]

        if len(sentences) <= self.max_sentences:
            return [text] if text.strip() else []

        chunks: list[str] = []
        i = 0
        while i < len(sentences):
            chunk_sents = sentences[i : i + self.max_sentences]
            chunks.append(" ".join(chunk_sents))
            i += self.max_sentences - self.overlap_sentences

        return chunks
