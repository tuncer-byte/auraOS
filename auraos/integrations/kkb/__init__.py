"""KKB integration module."""
from auraos.integrations.kkb.interface import KKBClient
from auraos.integrations.kkb.models import (
    CreditRecord,
    CreditReport,
    CreditScore,
    CreditType,
    InquiryRecord,
    PaymentRecord,
    PaymentStatus,
    RiskClass,
)
from auraos.integrations.kkb.stub import KKBStubClient

__all__ = [
    "KKBClient",
    "KKBStubClient",
    "CreditRecord",
    "CreditReport",
    "CreditScore",
    "CreditType",
    "InquiryRecord",
    "PaymentRecord",
    "PaymentStatus",
    "RiskClass",
]
