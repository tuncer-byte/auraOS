"""Tests for auraOS v0.3 - Integrations (MASAK, KKB)."""
import asyncio
import pytest
from datetime import date, datetime
from decimal import Decimal

from auraos.integrations.masak import (
    MASAKStubClient,
    SanctionMatch,
    PEPMatch,
    SARCase,
    SARStatus,
)
from auraos.integrations.kkb import (
    KKBStubClient,
    CreditScore,
    RiskClass,
    CreditRecord,
    CreditType,
)
from auraos.fintech.sar import SARCaseManager, Transaction


def run_async(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


class TestMASAKStubClient:
    """Tests for MASAK stub client."""

    @pytest.fixture
    def masak_client(self):
        return MASAKStubClient()

    def test_sanctions_screening_no_match(self, masak_client):
        results = run_async(masak_client.screen_sanctions("Mehmet Yilmaz"))
        assert isinstance(results, list)

    def test_sanctions_screening_with_match(self, masak_client):
        results = run_async(masak_client.screen_sanctions("Test Sanctioned Person"))
        assert len(results) > 0
        assert results[0].match_score >= 0.75
        assert results[0].list_name in ["UN", "OFAC", "EU", "MASAK"]

    def test_pep_screening(self, masak_client):
        results = run_async(masak_client.screen_pep("Test Politician", country="TR"))
        assert isinstance(results, list)

    def test_sar_filing(self, masak_client):
        case = SARCase(
            id="TEST-001",
            customer_id="12345678901",
            customer_name="Test Customer",
            suspicious_activity="Structuring",
            transaction_ids=["TXN001", "TXN002"],
            amount_total=Decimal("50000"),
            currency="TRY",
            detection_date=date.today(),
            detection_method="rule_based",
            risk_indicators=["structuring", "unusual_pattern"],
            narrative="Multiple transactions just below threshold.",
        )

        result = run_async(masak_client.file_sar(case))
        assert result.success is True
        assert result.filing_reference is not None
        assert result.filing_reference.startswith("MASAK-SAR-")

    def test_sar_status_query(self, masak_client):
        case = SARCase(
            id="TEST-002",
            customer_id="12345678901",
            customer_name="Test",
            suspicious_activity="Test",
            transaction_ids=["TXN001"],
            amount_total=Decimal("10000"),
            currency="TRY",
            detection_date=date.today(),
            detection_method="ai_agent",
            risk_indicators=["test"],
            narrative="Test case",
        )
        run_async(masak_client.file_sar(case))

        status = run_async(masak_client.get_sar_status("TEST-002"))
        assert status == SARStatus.FILED


class TestKKBStubClient:
    """Tests for KKB stub client."""

    @pytest.fixture
    def kkb_client(self):
        return KKBStubClient()

    def test_get_credit_score(self, kkb_client):
        score = run_async(kkb_client.get_credit_score("12345678901"))
        assert isinstance(score, CreditScore)
        assert 1 <= score.value <= 1900
        assert score.risk_class in RiskClass

    def test_credit_score_deterministic(self, kkb_client):
        score1 = run_async(kkb_client.get_credit_score("12345678901"))
        score2 = run_async(kkb_client.get_credit_score("12345678901"))
        assert score1.value == score2.value

    def test_get_credit_report(self, kkb_client):
        report = run_async(kkb_client.get_credit_report("12345678901", "CONSENT-123"))
        assert report.tc_kimlik == "12345678901"
        assert report.score is not None
        assert isinstance(report.active_credits, list)
        assert report.utilization_ratio >= 0

    def test_report_new_credit(self, kkb_client):
        credit = CreditRecord(
            account_id="NEW-001",
            credit_type=CreditType.CONSUMER,
            lender="Kuveyt Türk",
            opened_date=date.today(),
            credit_limit=Decimal("50000"),
            current_balance=Decimal("45000"),
            monthly_payment=Decimal("2083"),
            status="open",
        )

        result = run_async(kkb_client.report_new_credit(credit, "12345678901"))
        assert result is True

        report = run_async(kkb_client.get_credit_report("12345678901", "CONSENT-123"))
        account_ids = [c.account_id for c in report.active_credits]
        assert "NEW-001" in account_ids

    def test_set_custom_score(self, kkb_client):
        custom_score = CreditScore(
            value=1800,
            risk_class=RiskClass.A,
            factors=["Excellent history"],
        )
        kkb_client.set_score("99999999999", custom_score)

        retrieved = run_async(kkb_client.get_credit_score("99999999999"))
        assert retrieved.value == 1800
        assert retrieved.risk_class == RiskClass.A


class TestSARCaseManager:
    """Tests for SAR case management."""

    @pytest.fixture
    def sar_manager(self):
        masak = MASAKStubClient()
        return SARCaseManager(masak_client=masak)

    def test_create_case(self, sar_manager):
        transactions = [
            Transaction(
                id="TXN001",
                customer_id="12345",
                amount=Decimal("9500"),
                currency="TRY",
                transaction_type="transfer",
                timestamp=datetime.now(),
            ),
            Transaction(
                id="TXN002",
                customer_id="12345",
                amount=Decimal("9500"),
                currency="TRY",
                transaction_type="transfer",
                timestamp=datetime.now(),
            ),
        ]

        case = run_async(sar_manager.create_case(
            customer_id="12345",
            customer_name="Test Customer",
            transactions=transactions,
            detection_method="ai_agent",
            risk_indicators=["structuring", "multiple_small_transfers"],
        ))

        assert case.id.startswith("SAR-")
        assert case.status == SARStatus.DRAFT
        assert case.customer_id == "12345"
        assert len(case.transaction_ids) == 2

    def test_submit_for_review(self, sar_manager):
        transactions = [
            Transaction(
                id="TXN003",
                customer_id="12345",
                amount=Decimal("50000"),
                currency="TRY",
                transaction_type="cash",
                timestamp=datetime.now(),
            ),
        ]

        case = run_async(sar_manager.create_case(
            customer_id="12345",
            customer_name="Test",
            transactions=transactions,
            detection_method="rule",
            risk_indicators=["high_risk_cash"],
        ))

        result = run_async(sar_manager.submit_for_review(case.id, "reviewer1"))
        assert result is True

        updated_case = run_async(sar_manager.get_case(case.id))
        assert updated_case.status == SARStatus.SUBMITTED

    def test_approve_and_file(self, sar_manager):
        transactions = [
            Transaction(
                id="TXN004",
                customer_id="99999",
                amount=Decimal("100000"),
                currency="TRY",
                transaction_type="wire",
                timestamp=datetime.now(),
            ),
        ]

        case = run_async(sar_manager.create_case(
            customer_id="99999",
            customer_name="Suspicious Customer",
            transactions=transactions,
            detection_method="ai_agent",
            risk_indicators=["high_value", "no_economic_purpose"],
        ))

        result = run_async(sar_manager.approve_and_file(
            case.id,
            approver_id="compliance_officer",
            narrative="Detailed narrative of suspicious activity...",
        ))

        assert result.success is True
        assert result.filing_reference is not None

    def test_reject_case(self, sar_manager):
        transactions = [
            Transaction(
                id="TXN005",
                customer_id="11111",
                amount=Decimal("5000"),
                currency="TRY",
                transaction_type="payment",
                timestamp=datetime.now(),
            ),
        ]

        case = run_async(sar_manager.create_case(
            customer_id="11111",
            customer_name="False Positive",
            transactions=transactions,
            detection_method="rule",
            risk_indicators=["unusual_pattern"],
        ))

        result = run_async(sar_manager.reject_case(
            case.id,
            rejector_id="analyst",
            reason="False positive - legitimate business activity",
        ))
        assert result is True

        pending = run_async(sar_manager.get_pending_cases())
        case_ids = [c.id for c in pending]
        assert case.id not in case_ids

    def test_get_pending_cases(self, sar_manager):
        for i in range(3):
            transactions = [
                Transaction(
                    id=f"TXN10{i}",
                    customer_id=f"CUST{i}",
                    amount=Decimal("10000"),
                    currency="TRY",
                    transaction_type="transfer",
                    timestamp=datetime.now(),
                ),
            ]
            run_async(sar_manager.create_case(
                customer_id=f"CUST{i}",
                customer_name=f"Customer {i}",
                transactions=transactions,
                detection_method="batch",
                risk_indicators=["test"],
            ))

        pending = run_async(sar_manager.get_pending_cases())
        assert len(pending) >= 3
