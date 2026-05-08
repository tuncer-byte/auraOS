"""auraOS External Integrations.

This module provides interfaces and stub implementations for
external regulatory and financial data systems.

Integrations follow the Interface + Stub pattern:
- Abstract interface defines the contract
- Stub implementation for testing/development
- Real implementation for production

Available integrations:
- MASAK: Turkish Financial Crimes Investigation Board
- KKB: Turkish Credit Bureau (Kredi Kayıt Bürosu)
- TCMB: Central Bank of Turkey (coming soon)
"""
from auraos.integrations.masak import (
    MASAKClient,
    MASAKStubClient,
    PEPMatch,
    SanctionMatch,
    SARCase,
    SARFilingResult,
    SARStatus,
)
from auraos.integrations.kkb import (
    KKBClient,
    KKBStubClient,
    CreditRecord,
    CreditReport,
    CreditScore,
    CreditType,
    RiskClass,
)

__all__ = [
    # MASAK
    "MASAKClient",
    "MASAKStubClient",
    "PEPMatch",
    "SanctionMatch",
    "SARCase",
    "SARFilingResult",
    "SARStatus",
    # KKB
    "KKBClient",
    "KKBStubClient",
    "CreditRecord",
    "CreditReport",
    "CreditScore",
    "CreditType",
    "RiskClass",
]
