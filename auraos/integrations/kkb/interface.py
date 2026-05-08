"""KKB (Kredi Kayıt Bürosu) client interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auraos.integrations.kkb.models import (
        CreditRecord,
        CreditReport,
        CreditScore,
    )


class KKBClient(ABC):
    """Abstract interface for KKB (Kredi Kayıt Bürosu) integration.

    KKB is Turkey's credit bureau, similar to Experian/Equifax.

    This interface defines the contract for:
    - Credit score queries
    - Full credit report access
    - Credit reporting (new accounts, updates)

    Implementations:
    - KKBStubClient: For testing/development
    - KKBRealClient: For production (connects to real KKB systems)
    """

    @abstractmethod
    async def get_credit_score(
        self,
        tc_kimlik: str,
        consent_id: str | None = None,
    ) -> "CreditScore":
        """Get credit score for a customer.

        Args:
            tc_kimlik: Turkish national ID (TC Kimlik No)
            consent_id: Customer consent reference

        Returns:
            Credit score with risk class
        """
        ...

    @abstractmethod
    async def get_credit_report(
        self,
        tc_kimlik: str,
        consent_id: str,
    ) -> "CreditReport":
        """Get full credit report for a customer.

        Args:
            tc_kimlik: Turkish national ID
            consent_id: Customer consent reference (required)

        Returns:
            Full credit report with history
        """
        ...

    @abstractmethod
    async def report_new_credit(
        self,
        credit: "CreditRecord",
        tc_kimlik: str,
    ) -> bool:
        """Report a new credit to KKB.

        Args:
            credit: The credit record to report
            tc_kimlik: Customer's TC Kimlik No

        Returns:
            True if reported successfully
        """
        ...

    @abstractmethod
    async def update_credit_status(
        self,
        account_id: str,
        tc_kimlik: str,
        new_balance: float,
        payment_status: str,
    ) -> bool:
        """Update credit status (monthly reporting).

        Args:
            account_id: Credit account ID
            tc_kimlik: Customer's TC Kimlik No
            new_balance: Current balance
            payment_status: Payment status for the period

        Returns:
            True if updated successfully
        """
        ...
