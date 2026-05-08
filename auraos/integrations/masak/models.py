"""MASAK integration models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class SARStatus(str, Enum):
    """SAR case status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    FILED = "filed"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass
class SanctionMatch:
    """Result of a sanctions screening match."""
    list_name: str  # UN, OFAC, EU, MASAK
    matched_name: str
    match_score: float  # 0-1
    list_id: str
    sanctions_type: str
    effective_date: date
    country: str = ""
    aliases: list[str] = field(default_factory=list)
    identifiers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "list_name": self.list_name,
            "matched_name": self.matched_name,
            "match_score": self.match_score,
            "list_id": self.list_id,
            "sanctions_type": self.sanctions_type,
            "effective_date": self.effective_date.isoformat(),
            "country": self.country,
            "aliases": self.aliases,
            "identifiers": self.identifiers,
        }


@dataclass
class PEPMatch:
    """Result of a PEP (Politically Exposed Person) screening match."""
    name: str
    position: str
    country: str
    match_score: float
    level: str  # national, regional, local
    status: str  # active, former
    start_date: date | None = None
    end_date: date | None = None
    relatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "position": self.position,
            "country": self.country,
            "match_score": self.match_score,
            "level": self.level,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "relatives": self.relatives,
        }


@dataclass
class SARCase:
    """Suspicious Activity Report (Şüpheli İşlem Bildirimi) case."""
    id: str
    customer_id: str
    customer_name: str
    suspicious_activity: str
    transaction_ids: list[str]
    amount_total: Decimal
    currency: str
    detection_date: date
    detection_method: str
    risk_indicators: list[str]
    narrative: str
    attachments: list[str] = field(default_factory=list)
    status: SARStatus = SARStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    filed_at: datetime | None = None
    filing_reference: str | None = None
    approver: str | None = None
    reviewer_notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "suspicious_activity": self.suspicious_activity,
            "transaction_ids": self.transaction_ids,
            "amount_total": str(self.amount_total),
            "currency": self.currency,
            "detection_date": self.detection_date.isoformat(),
            "detection_method": self.detection_method,
            "risk_indicators": self.risk_indicators,
            "narrative": self.narrative,
            "attachments": self.attachments,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "filing_reference": self.filing_reference,
            "approver": self.approver,
            "reviewer_notes": self.reviewer_notes,
            "metadata": self.metadata,
        }


@dataclass
class SARFilingResult:
    """Result of filing a SAR."""
    success: bool
    case_id: str
    filing_reference: str | None = None
    filed_at: datetime | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "case_id": self.case_id,
            "filing_reference": self.filing_reference,
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "error": self.error,
            "warnings": self.warnings,
        }
