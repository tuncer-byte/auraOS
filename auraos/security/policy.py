"""
Policy System — yapılandırılabilir güvenlik kuralları.

Her policy birden fazla kural içerir. Kurallar text üzerinde
sırayla uygulanır ve aksiyon türüne göre farklı işlem yapılır:
  - BLOCK: Metni bloke et, işlemi durdur
  - ANONYMIZE: PII'yi token'la (Anonymizer ile)
  - REPLACE: Eşleşmeyi sabit metin ile değiştir
  - LOG: Sadece logla, metne dokunma
  - RAISE: Exception fırlat
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from auraos.guardrails import Anonymizer


class PolicyAction(str, Enum):
    BLOCK = "block"
    ANONYMIZE = "anonymize"
    REPLACE = "replace"
    LOG = "log"
    RAISE = "raise"


@dataclass
class PolicyRule:
    name: str
    pattern: re.Pattern
    action: PolicyAction
    replacement: str = "[REDACTED]"
    description: str = ""


@dataclass
class PolicyResult:
    ok: bool = True
    text: str = ""
    hits: list[dict] = field(default_factory=list)
    blocked: bool = False


@dataclass
class Policy:
    name: str
    rules: list[PolicyRule] = field(default_factory=list)

    def apply(
        self, text: str, anonymizer: Optional[Anonymizer] = None
    ) -> PolicyResult:
        hits: list[dict] = []
        result_text = text
        blocked = False

        for rule in self.rules:
            matches = list(rule.pattern.finditer(result_text))
            if not matches:
                continue

            for m in matches:
                hits.append({
                    "rule": rule.name,
                    "action": rule.action.value,
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                })

            if rule.action == PolicyAction.BLOCK:
                blocked = True

            elif rule.action == PolicyAction.REPLACE:
                result_text = rule.pattern.sub(rule.replacement, result_text)

            elif rule.action == PolicyAction.ANONYMIZE:
                if anonymizer:
                    result_text, _ = anonymizer.anonymize(result_text)
                else:
                    result_text = rule.pattern.sub(rule.replacement, result_text)

            elif rule.action == PolicyAction.RAISE:
                from auraos.exceptions import GuardrailError
                raise GuardrailError(
                    f"Policy violation: {rule.name}",
                    details={"hits": hits},
                )

        return PolicyResult(
            ok=not blocked and len(hits) == 0,
            text=result_text,
            hits=hits,
            blocked=blocked,
        )


def pii_policy(action: PolicyAction = PolicyAction.ANONYMIZE) -> Policy:
    return Policy(
        name="pii",
        rules=[
            PolicyRule(
                name="tc_kimlik",
                pattern=re.compile(r"\b[1-9]\d{10}\b"),
                action=action,
                description="TC Kimlik No",
            ),
            PolicyRule(
                name="iban",
                pattern=re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b", re.IGNORECASE),
                action=action,
                description="IBAN",
            ),
            PolicyRule(
                name="credit_card",
                pattern=re.compile(r"\b(?:\d[\s\-]?){13,19}\b"),
                action=action,
                description="Kredi Kartı",
            ),
            PolicyRule(
                name="email",
                pattern=re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
                action=action,
                description="E-posta",
            ),
            PolicyRule(
                name="phone_tr",
                pattern=re.compile(r"(?:\+?90|0)?[\s\-]?5\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
                action=action,
                description="Telefon (TR)",
            ),
        ],
    )


def financial_data_policy(action: PolicyAction = PolicyAction.ANONYMIZE) -> Policy:
    return Policy(
        name="financial_data",
        rules=[
            PolicyRule(
                name="iban",
                pattern=re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b", re.IGNORECASE),
                action=action,
                description="IBAN",
            ),
            PolicyRule(
                name="credit_card",
                pattern=re.compile(r"\b(?:\d[\s\-]?){13,19}\b"),
                action=action,
                description="Kredi Kartı",
            ),
            PolicyRule(
                name="balance",
                pattern=re.compile(
                    r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:TL|₺|USD|\$|EUR|€)",
                    re.IGNORECASE,
                ),
                action=action,
                description="Hesap Bakiyesi",
            ),
            PolicyRule(
                name="salary",
                pattern=re.compile(
                    r"(?:maaş|ücret|gelir)\s*[:=]?\s*\d+",
                    re.IGNORECASE,
                ),
                action=action,
                description="Maaş/Gelir Bilgisi",
            ),
        ],
    )


def prompt_injection_policy() -> Policy:
    return Policy(
        name="prompt_injection",
        rules=[
            PolicyRule(
                name="ignore_previous",
                pattern=re.compile(r"ignore\s+(all\s+)?previous\s+(instructions?|prompts?)", re.IGNORECASE),
                action=PolicyAction.BLOCK,
                description="Prompt injection: ignore previous",
            ),
            PolicyRule(
                name="disregard",
                pattern=re.compile(r"disregard\s+(your|all|previous)\s+(instructions|rules|prompt)", re.IGNORECASE),
                action=PolicyAction.BLOCK,
                description="Prompt injection: disregard",
            ),
            PolicyRule(
                name="system_prompt",
                pattern=re.compile(r"system\s+prompt[:\s]", re.IGNORECASE),
                action=PolicyAction.BLOCK,
                description="Prompt injection: system prompt",
            ),
            PolicyRule(
                name="role_change",
                pattern=re.compile(r"you\s+are\s+now\s+a\s+", re.IGNORECASE),
                action=PolicyAction.BLOCK,
                description="Prompt injection: role change",
            ),
        ],
    )
