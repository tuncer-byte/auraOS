"""SAR (Suspicious Activity Report) Case Management."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auraos.integrations.masak import MASAKClient, SARCase, SARFilingResult, SARStatus
    from auraos.observability.audit import AuditLog


@dataclass
class Transaction:
    """Transaction record for SAR analysis."""
    id: str
    customer_id: str
    amount: Decimal
    currency: str
    transaction_type: str
    timestamp: datetime
    counterparty: str | None = None
    description: str | None = None


class SARCaseManager:
    """Manages SAR case lifecycle from detection to filing."""

    def __init__(
        self,
        masak_client: "MASAKClient",
        audit_log: "AuditLog | None" = None,
    ) -> None:
        self.masak_client = masak_client
        self.audit_log = audit_log
        self._pending_cases: dict[str, "SARCase"] = {}

    async def create_case(
        self,
        customer_id: str,
        customer_name: str,
        transactions: list[Transaction],
        detection_method: str,
        risk_indicators: list[str],
        suspicious_activity: str | None = None,
    ) -> "SARCase":
        """Create a new SAR case.

        Args:
            customer_id: Customer identifier
            customer_name: Customer full name
            transactions: List of suspicious transactions
            detection_method: How the activity was detected
            risk_indicators: List of AML risk indicators

        Returns:
            Created SAR case
        """
        from auraos.integrations.masak.models import SARCase, SARStatus

        case_id = f"SAR-{uuid.uuid4().hex[:8].upper()}"

        amount_total = sum(t.amount for t in transactions)
        currency = transactions[0].currency if transactions else "TRY"

        case = SARCase(
            id=case_id,
            customer_id=customer_id,
            customer_name=customer_name,
            suspicious_activity=suspicious_activity or self._generate_activity_summary(transactions, risk_indicators),
            transaction_ids=[t.id for t in transactions],
            amount_total=amount_total,
            currency=currency,
            detection_date=date.today(),
            detection_method=detection_method,
            risk_indicators=risk_indicators,
            narrative="",
            status=SARStatus.DRAFT,
        )

        self._pending_cases[case_id] = case

        if self.audit_log:
            self.audit_log.record(
                action="sar.case_created",
                actor="system",
                resource=case_id,
                detail={
                    "customer_id": customer_id,
                    "transaction_count": len(transactions),
                    "amount_total": str(amount_total),
                    "risk_indicators": risk_indicators,
                },
            )

        return case

    def _generate_activity_summary(
        self,
        transactions: list[Transaction],
        risk_indicators: list[str],
    ) -> str:
        """Generate activity summary from transactions and indicators."""
        total = sum(t.amount for t in transactions)
        types = set(t.transaction_type for t in transactions)

        summary = f"{len(transactions)} adet işlem tespit edildi. "
        summary += f"Toplam tutar: {total} TRY. "
        summary += f"İşlem türleri: {', '.join(types)}. "
        summary += f"Risk göstergeleri: {', '.join(risk_indicators)}."

        return summary

    async def submit_for_review(
        self,
        case_id: str,
        reviewer_id: str,
    ) -> bool:
        """Submit a case for compliance review.

        Args:
            case_id: SAR case ID
            reviewer_id: ID of the reviewer to assign

        Returns:
            True if submitted successfully
        """
        from auraos.integrations.masak.models import SARStatus

        case = self._pending_cases.get(case_id)
        if not case:
            return False

        case.status = SARStatus.SUBMITTED
        case.metadata["reviewer_id"] = reviewer_id
        case.metadata["submitted_at"] = datetime.now().isoformat()

        if self.audit_log:
            self.audit_log.record(
                action="sar.submitted_for_review",
                actor="system",
                resource=case_id,
                detail={"reviewer_id": reviewer_id},
            )

        return True

    async def approve_and_file(
        self,
        case_id: str,
        approver_id: str,
        narrative: str,
    ) -> "SARFilingResult":
        """Approve a case and file it with MASAK.

        Args:
            case_id: SAR case ID
            approver_id: ID of the approving officer
            narrative: Detailed narrative for the SAR

        Returns:
            Filing result from MASAK
        """
        from auraos.integrations.masak.models import SARFilingResult

        case = self._pending_cases.get(case_id)
        if not case:
            return SARFilingResult(
                success=False,
                case_id=case_id,
                error=f"Case {case_id} not found",
            )

        case.narrative = narrative
        case.approver = approver_id

        result = await self.masak_client.file_sar(case)

        if result.success:
            del self._pending_cases[case_id]

            if self.audit_log:
                self.audit_log.record(
                    action="sar.filed",
                    actor=approver_id,
                    resource=case_id,
                    detail={
                        "filing_reference": result.filing_reference,
                        "customer_id": case.customer_id,
                    },
                )
        else:
            if self.audit_log:
                self.audit_log.record(
                    action="sar.filing_failed",
                    actor=approver_id,
                    resource=case_id,
                    detail={"error": result.error},
                )

        return result

    async def reject_case(
        self,
        case_id: str,
        rejector_id: str,
        reason: str,
    ) -> bool:
        """Reject a SAR case (false positive).

        Args:
            case_id: SAR case ID
            rejector_id: ID of the rejecting officer
            reason: Reason for rejection

        Returns:
            True if rejected successfully
        """
        from auraos.integrations.masak.models import SARStatus

        case = self._pending_cases.get(case_id)
        if not case:
            return False

        case.status = SARStatus.REJECTED
        case.reviewer_notes = reason
        case.metadata["rejected_by"] = rejector_id
        case.metadata["rejected_at"] = datetime.now().isoformat()

        if self.audit_log:
            self.audit_log.record(
                action="sar.rejected",
                actor=rejector_id,
                resource=case_id,
                detail={"reason": reason},
            )

        del self._pending_cases[case_id]
        return True

    async def get_pending_cases(self) -> list["SARCase"]:
        """Get all pending SAR cases."""
        return list(self._pending_cases.values())

    async def get_case(self, case_id: str) -> "SARCase | None":
        """Get a specific case by ID."""
        return self._pending_cases.get(case_id) or await self.masak_client.get_sar(case_id)
