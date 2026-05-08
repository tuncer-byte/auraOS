"""Gerçek LLM gerektiren test'ler için ortak fixture'lar.

Hiçbir mock yok: GEMINI_API_KEY (veya GOOGLE_API_KEY) yoksa LLM-bağımlı testler
`pytest.skip` ile atlanır. CI'da key tanımlıysa entegrasyon olarak çalışır.
"""
from __future__ import annotations

import os

import pytest


def _has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


requires_llm = pytest.mark.skipif(
    not _has_gemini_key(),
    reason="GEMINI_API_KEY/GOOGLE_API_KEY tanımlı değil; gerçek LLM testi atlandı.",
)


@pytest.fixture
def gemini_llm():
    """Gerçek Gemini provider; key yoksa test skip edilir."""
    if not _has_gemini_key():
        pytest.skip("GEMINI_API_KEY/GOOGLE_API_KEY tanımlı değil")
    from auraos.llm.factory import get_llm
    return get_llm("gemini/gemini-2.5-flash")
