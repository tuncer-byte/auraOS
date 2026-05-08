"""KKB stub client for testing."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import random

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


class KKBStubClient(KKBClient):
    """Stub implementation for testing and development.

    Pre-loaded with realistic test data for Turkish banking scenarios.
    """

    def __init__(
        self,
        credit_scores: dict[str, CreditScore] | None = None,
        credit_records: dict[str, list[CreditRecord]] | None = None,
    ) -> None:
        self._scores = credit_scores or {}
        self._records = credit_records or {}
        self._inquiries: dict[str, list[InquiryRecord]] = {}
        self._reported_credits: list[tuple[str, CreditRecord]] = []

    def _generate_score(self, tc_kimlik: str) -> CreditScore:
        """Generate a deterministic score based on TC."""
        seed = sum(ord(c) for c in tc_kimlik)
        random.seed(seed)

        score = random.randint(1100, 1850)

        if score >= 1700:
            risk_class = RiskClass.A
            factors = ["Excellent payment history", "Long credit history"]
        elif score >= 1500:
            risk_class = RiskClass.B
            factors = ["Good payment history", "Moderate utilization"]
        elif score >= 1300:
            risk_class = RiskClass.C
            factors = ["Some late payments", "High utilization"]
        elif score >= 1100:
            risk_class = RiskClass.D
            factors = ["Multiple late payments", "Recent negative records"]
        else:
            risk_class = RiskClass.E
            factors = ["Defaults", "Collections", "High risk"]

        return CreditScore(
            value=score,
            risk_class=risk_class,
            factors=factors,
            confidence=0.95,
        )

    def _generate_records(self, tc_kimlik: str) -> list[CreditRecord]:
        """Generate sample credit records."""
        seed = sum(ord(c) for c in tc_kimlik)
        random.seed(seed)

        records = []
        num_records = random.randint(1, 4)

        for i in range(num_records):
            credit_type = random.choice(list(CreditType))
            opened = date(
                random.randint(2018, 2024),
                random.randint(1, 12),
                random.randint(1, 28),
            )

            limit = Decimal(str(random.randint(5000, 100000)))
            balance = Decimal(str(random.randint(0, int(limit))))

            payment_history = []
            for month_offset in range(12):
                period_date = date(2026, 5, 1)
                period_date = date(
                    period_date.year if period_date.month > month_offset else period_date.year - 1,
                    (period_date.month - month_offset - 1) % 12 + 1,
                    1,
                )
                status = random.choices(
                    [PaymentStatus.CURRENT, PaymentStatus.LATE_30, PaymentStatus.LATE_60],
                    weights=[0.85, 0.10, 0.05],
                )[0]
                payment_history.append(PaymentRecord(
                    period=period_date.strftime("%Y-%m"),
                    status=status,
                    amount_due=Decimal("1000"),
                    amount_paid=Decimal("1000") if status == PaymentStatus.CURRENT else Decimal("0"),
                    days_late=0 if status == PaymentStatus.CURRENT else 30,
                ))

            records.append(CreditRecord(
                account_id=f"KKB-{tc_kimlik[:4]}-{i:03d}",
                credit_type=credit_type,
                lender="Test Bank",
                opened_date=opened,
                credit_limit=limit,
                current_balance=balance,
                monthly_payment=Decimal(str(int(limit / 24))),
                status="open",
                payment_history=payment_history,
            ))

        return records

    async def get_credit_score(
        self,
        tc_kimlik: str,
        consent_id: str | None = None,
    ) -> CreditScore:
        if tc_kimlik in self._scores:
            return self._scores[tc_kimlik]
        return self._generate_score(tc_kimlik)

    async def get_credit_report(
        self,
        tc_kimlik: str,
        consent_id: str,
    ) -> CreditReport:
        score = await self.get_credit_score(tc_kimlik, consent_id)
        records = self._records.get(tc_kimlik) or self._generate_records(tc_kimlik)
        inquiries = self._inquiries.get(tc_kimlik, [])

        inquiries.append(InquiryRecord(
            inquiry_date=date.today(),
            inquirer="Test Bank",
            inquiry_type="account_review",
            consent_id=consent_id,
        ))

        active = [r for r in records if r.status == "open"]
        closed = [r for r in records if r.status != "open"]

        total_debt = sum(r.current_balance for r in active)
        total_limit = sum(r.credit_limit for r in active)
        utilization = float(total_debt / total_limit) if total_limit > 0 else 0.0

        oldest = min((r.opened_date for r in records), default=None)

        negative = sum(
            1 for r in records
            for p in r.payment_history
            if p.status in (PaymentStatus.LATE_60, PaymentStatus.LATE_90, PaymentStatus.DEFAULT)
        )

        return CreditReport(
            tc_kimlik=tc_kimlik,
            score=score,
            active_credits=active,
            closed_credits=closed,
            inquiries=inquiries,
            total_debt=total_debt,
            total_credit_limit=total_limit,
            utilization_ratio=utilization,
            oldest_account_date=oldest,
            negative_records=negative,
        )

    async def report_new_credit(
        self,
        credit: CreditRecord,
        tc_kimlik: str,
    ) -> bool:
        self._reported_credits.append((tc_kimlik, credit))
        if tc_kimlik not in self._records:
            self._records[tc_kimlik] = []
        self._records[tc_kimlik].append(credit)
        return True

    async def update_credit_status(
        self,
        account_id: str,
        tc_kimlik: str,
        new_balance: float,
        payment_status: str,
    ) -> bool:
        records = self._records.get(tc_kimlik, [])
        for record in records:
            if record.account_id == account_id:
                record.current_balance = Decimal(str(new_balance))
                record.payment_history.append(PaymentRecord(
                    period=date.today().strftime("%Y-%m"),
                    status=PaymentStatus(payment_status),
                    amount_due=record.monthly_payment,
                    amount_paid=record.monthly_payment if payment_status == "current" else Decimal("0"),
                ))
                return True
        return False

    def set_score(self, tc_kimlik: str, score: CreditScore) -> None:
        """Set a specific score for testing."""
        self._scores[tc_kimlik] = score

    def set_records(self, tc_kimlik: str, records: list[CreditRecord]) -> None:
        """Set specific records for testing."""
        self._records[tc_kimlik] = records
