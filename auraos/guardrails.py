"""
Guardrails - güvenlik katmanı.

Modüller:
  - PII detection / redaction (TC kimlik, IBAN, kart, telefon, email)
  - Prompt injection sezgisel tarama
  - Output validation (yasak kelimeler)

Bütün checker'lar dict döner: {ok: bool, redacted: str, hits: [...]}.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from auraos.exceptions import PIIDetectedError, PromptInjectionError


# ---- PII pattern'leri ----
_PII_PATTERNS = {
    "tc_kimlik": re.compile(r"\b[1-9]\d{10}\b"),
    "iban": re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b", re.IGNORECASE),
    "credit_card": re.compile(r"\b(?:\d[\s\-]?){13,19}\b"),
    "email": re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "phone_tr": re.compile(r"(?:\+?90|0)?[\s\-]?5\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
}


# ---- Prompt injection sezgisel tetikleyiciler ----
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+(instructions?|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+(your|all|previous)\s+(instructions|rules|prompt)", re.IGNORECASE),
    re.compile(r"system\s+prompt[:\s]", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions)", re.IGNORECASE),
    re.compile(r"önceki\s+(talimat|komut|kural).{0,15}(yok\s*say|unut|gözardı)", re.IGNORECASE),
    re.compile(r"sistem\s+prompt", re.IGNORECASE),
    re.compile(r"sen\s+artık.{0,30}(asistan|sistem|model)", re.IGNORECASE),
]


@dataclass
class GuardrailResult:
    ok: bool = True
    text: str = ""
    hits: list[dict] = field(default_factory=list)
    reason: Optional[str] = None


def detect_pii(text: str) -> list[dict]:
    hits: list[dict] = []
    for kind, pattern in _PII_PATTERNS.items():
        for m in pattern.finditer(text):
            hits.append({"type": kind, "match": m.group(0), "span": [m.start(), m.end()]})
    return hits


def redact_pii(text: str, mask: str = "[REDACTED]") -> tuple[str, list[dict]]:
    hits = detect_pii(text)
    if not hits:
        return text, []
    # Çakışan span'leri merge et: en uzun match kazansın
    spans = sorted([(h["span"][0], h["span"][1]) for h in hits])
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out: list[str] = []
    cursor = 0
    for s, e in merged:
        out.append(text[cursor:s])
        out.append(mask)
        cursor = e
    out.append(text[cursor:])
    return "".join(out), hits


def detect_prompt_injection(text: str) -> list[dict]:
    hits: list[dict] = []
    for pat in _INJECTION_PATTERNS:
        for m in pat.finditer(text):
            hits.append({"pattern": pat.pattern, "match": m.group(0)})
    return hits


@dataclass
class Guardrails:
    """
    Guardrail pipeline. agent.run / arun başında ve sonunda çağrılır.

    Args:
        pii_redact: çıktıdaki PII'yi maskele.
        block_prompt_injection: kullanıcı girdisinde injection tespit edilirse engelle.
        raise_on_violation: True ise hata fırlat, False ise sadece flag'le.
    """

    pii_redact: bool = True
    block_prompt_injection: bool = True
    raise_on_violation: bool = False

    def check_input(self, text: str) -> GuardrailResult:
        if not self.block_prompt_injection:
            return GuardrailResult(ok=True, text=text)
        hits = detect_prompt_injection(text)
        if not hits:
            return GuardrailResult(ok=True, text=text)
        result = GuardrailResult(ok=False, text=text, hits=hits, reason="prompt_injection")
        if self.raise_on_violation:
            raise PromptInjectionError("Prompt injection denemesi tespit edildi", details={"hits": hits})
        return result

    def check_output(self, text: str) -> GuardrailResult:
        if not self.pii_redact:
            return GuardrailResult(ok=True, text=text)
        redacted, hits = redact_pii(text)
        if not hits:
            return GuardrailResult(ok=True, text=text)
        if self.raise_on_violation:
            raise PIIDetectedError("Çıktıda PII tespit edildi", details={"hits": hits})
        return GuardrailResult(ok=False, text=redacted, hits=hits, reason="pii")
