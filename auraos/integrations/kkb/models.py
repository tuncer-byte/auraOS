"""KKB (Kredi Kayıt Bürosu) integration models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class RiskClass(str, Enum):
    """Credit risk classification."""
    A = "A"  # Excellent (1700-1900)
    B = "B"  # Good (1500-1699)
    C = "C"  # Fair (1300-1499)
    D = "D"  # Poor (1100-1299)
    E = "E"  # Very Poor (1-1099)


class CreditType(str, Enum):
    """Type of credit product."""
    MORTGAGE = "mortgage"
    AUTO = "auto"
    CONSUMER = "consumer"
    CREDIT_CARD = "credit_card"
    COMMERCIAL = "commercial"
    OVERDRAFT = "overdraft"


class PaymentStatus(str, Enum):
    """Payment status for a period."""
    CURRENT = "current"  # On time
    LATE_30 = "late_30"  # 1-30 days late
    LATE_60 = "late_60"  # 31-60 days late
    LATE_90 = "late_90"  # 61-90 days late
    LATE_120 = "late_120"  # 91-120 days late
    DEFAULT = "default"  # 120+ days / written off
    RESTRUCTURED = "restructured"


@dataclass
class CreditScore:
    """Credit score result."""
    value: int  # 1-1900
    risk_class: RiskClass
    factors: list[str] = field(default_factory=list)
    confidence: float = 1.0
    calculated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "risk_class": self.risk_class.value,
            "factors": self.factors,
            "confidence": self.confidence,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class PaymentRecord:
    """Monthly payment record."""
    period: str  # YYYY-MM
    status: PaymentStatus
    amount_due: Decimal
    amount_paid: Decimal
    days_late: int = 0

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "status": self.status.value,
            "amount_due": str(self.amount_due),
            "amount_paid": str(self.amount_paid),
            "days_late": self.days_late,
        }


@dataclass
class CreditRecord:
    """Individual credit account record."""
    account_id: str
    credit_type: CreditType
    lender: str
    opened_date: date
    credit_limit: Decimal
    current_balance: Decimal
    monthly_payment: Decimal
    status: str  # open, closed, written_off
    currency: str = "TRY"
    closed_date: date | None = None
    payment_history: list[PaymentRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "credit_type": self.credit_type.value,
            "lender": self.lender,
            "opened_date": self.opened_date.isoformat(),
            "credit_limit": str(self.credit_limit),
            "current_balance": str(self.current_balance),
            "monthly_payment": str(self.monthly_payment),
            "status": self.status,
            "currency": self.currency,
            "closed_date": self.closed_date.isoformat() if self.closed_date else None,
            "payment_history": [p.to_dict() for p in self.payment_history[-12:]],
        }


@dataclass
class InquiryRecord:
    """Credit inquiry record."""
    inquiry_date: date
    inquirer: str
    inquiry_type: str  # new_credit, account_review, pre_approval
    consent_id: str

    def to_dict(self) -> dict:
        return {
            "inquiry_date": self.inquiry_date.isoformat(),
            "inquirer": self.inquirer,
            "inquiry_type": self.inquiry_type,
            "consent_id": self.consent_id,
        }


@dataclass
class CreditReport:
    """Full credit report from KKB."""
    tc_kimlik: str
    score: CreditScore
    active_credits: list[CreditRecord] = field(default_factory=list)
    closed_credits: list[CreditRecord] = field(default_factory=list)
    inquiries: list[InquiryRecord] = field(default_factory=list)
    report_date: datetime = field(default_factory=datetime.now)
    total_debt: Decimal = Decimal("0")
    total_credit_limit: Decimal = Decimal("0")
    utilization_ratio: float = 0.0
    oldest_account_date: date | None = None
    negative_records: int = 0

    def to_dict(self) -> dict:
        return {
            "tc_kimlik": self.tc_kimlik,
            "score": self.score.to_dict(),
            "active_credits": [c.to_dict() for c in self.active_credits],
            "closed_credits": [c.to_dict() for c in self.closed_credits[:5]],
            "inquiries": [i.to_dict() for i in self.inquiries[:10]],
            "report_date": self.report_date.isoformat(),
            "total_debt": str(self.total_debt),
            "total_credit_limit": str(self.total_credit_limit),
            "utilization_ratio": self.utilization_ratio,
            "oldest_account_date": self.oldest_account_date.isoformat() if self.oldest_account_date else None,
            "negative_records": self.negative_records,
        }
