"""Basit text chunk'layıcı."""
from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Metni chunk_size karakterlik parçalara böl, overlap ile."""
    if chunk_size <= 0:
        return [text]
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size - overlap
        if i < 0:
            break
    return chunks
