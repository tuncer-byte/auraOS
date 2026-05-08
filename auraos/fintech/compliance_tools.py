"""Compliance tools for AML, sanctions, and credit operations.

These tools use ToolExecutionContext to access integration services.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from auraos.tools.decorator import tool


@tool(composable=True, description="MASAK/OFAC/UN yaptırım listelerini gerçek zamanlı tarar.")
async def check_sanctions_realtime(
    name: str,
    birth_date: str | None = None,
    id_number: str | None = None,
    country: str | None = None,
    ctx: Any = None,
) -> dict:
    """Screen against sanctions lists in real-time.

    Args:
        name: Name to screen
        birth_date: Date of birth (YYYY-MM-DD) for better matching
        id_number: ID number (TC, passport)
        country: Country code
        ctx: ToolExecutionContext (injected)

    Returns:
        Screening results with matches
    """
    from auraos.integrations.masak import MASAKClient

    if ctx is None:
        return {"error": "Context required", "has_match": False}

    masak = ctx.get_service(MASAKClient)
    bd = date.fromisoformat(birth_date) if birth_date else None

    matches = await masak.screen_sanctions(
        name=name,
        birth_date=bd,
        id_number=id_number,
        country=country,
    )

    return {
        "has_match": len(matches) > 0,
        "match_count": len(matches),
        "matches": [m.to_dict() for m in matches[:5]],
        "screened_at": datetime.now().isoformat(),
        "screened_name": name,
    }


@tool(composable=True, description="PEP (siyasi olarak ifşa olmuş kişi) taraması yapar.")
async def check_pep(
    name: str,
    country: str = "TR",
    ctx: Any = None,
) -> dict:
    """Screen for Politically Exposed Persons.

    Args:
        name: Name to screen
        country: Country code (default: TR)
        ctx: ToolExecutionContext (injected)

    Returns:
        PEP screening results
    """
    from auraos.integrations.masak import MASAKClient

    if ctx is None:
        return {"error": "Context required", "has_match": False}

    masak = ctx.get_service(MASAKClient)
    matches = await masak.screen_pep(name=name, country=country)

    return {
        "has_match": len(matches) > 0,
        "match_count": len(matches),
        "matches": [m.to_dict() for m in matches[:5]],
        "screened_at": datetime.now().isoformat(),
    }


@tool(composable=True, description="KKB'den kredi skoru sorgular.")
async def get_credit_score(
    tc_kimlik: str,
    consent_id: str | None = None,
    ctx: Any = None,
) -> dict:
    """Get credit score from KKB.

    Args:
        tc_kimlik: Turkish national ID
        consent_id: Customer consent reference
        ctx: ToolExecutionContext (injected)

    Returns:
        Credit score with risk class
    """
    from auraos.integrations.kkb import KKBClient

    if ctx is None:
        return {"error": "Context required"}

    kkb = ctx.get_service(KKBClient)
    score = await kkb.get_credit_score(tc_kimlik, consent_id)

    return {
        "score": score.value,
        "risk_class": score.risk_class.value,
        "factors": score.factors,
        "confidence": score.confidence,
        "queried_at": datetime.now().isoformat(),
    }


@tool(composable=True, description="KKB'den detaylı kredi raporu alır.")
async def get_credit_report(
    tc_kimlik: str,
    consent_id: str,
    ctx: Any = None,
) -> dict:
    """Get full credit report from KKB.

    Args:
        tc_kimlik: Turkish national ID
        consent_id: Customer consent reference (required)
        ctx: ToolExecutionContext (injected)

    Returns:
        Full credit report summary
    """
    from auraos.integrations.kkb import KKBClient

    if ctx is None:
        return {"error": "Context required"}

    kkb = ctx.get_service(KKBClient)
    report = await kkb.get_credit_report(tc_kimlik, consent_id)

    return {
        "score": report.score.to_dict(),
        "active_credit_count": len(report.active_credits),
        "total_debt": str(report.total_debt),
        "total_credit_limit": str(report.total_credit_limit),
        "utilization_ratio": round(report.utilization_ratio * 100, 1),
        "negative_records": report.negative_records,
        "oldest_account_date": report.oldest_account_date.isoformat() if report.oldest_account_date else None,
        "recent_inquiries": len(report.inquiries),
        "report_date": report.report_date.isoformat(),
    }


@tool(composable=True, description="Yeni SAR (Şüpheli İşlem Bildirimi) oluşturur.")
async def create_sar_case(
    customer_id: str,
    customer_name: str,
    transaction_ids: list[str],
    risk_indicators: list[str],
    suspicious_activity: str,
    ctx: Any = None,
) -> dict:
    """Create a new SAR case.

    Args:
        customer_id: Customer identifier
        customer_name: Customer full name
        transaction_ids: List of suspicious transaction IDs
        risk_indicators: List of AML risk indicators
        suspicious_activity: Description of suspicious activity
        ctx: ToolExecutionContext (injected)

    Returns:
        Created SAR case details
    """
    from auraos.fintech.sar import SARCaseManager, Transaction
    from decimal import Decimal

    if ctx is None:
        return {"error": "Context required"}

    manager = ctx.get_service(SARCaseManager)

    transactions = [
        Transaction(
            id=tid,
            customer_id=customer_id,
            amount=Decimal("0"),
            currency="TRY",
            transaction_type="unknown",
            timestamp=datetime.now(),
        )
        for tid in transaction_ids
    ]

    case = await manager.create_case(
        customer_id=customer_id,
        customer_name=customer_name,
        transactions=transactions,
        detection_method="ai_agent",
        risk_indicators=risk_indicators,
        suspicious_activity=suspicious_activity,
    )

    return {
        "case_id": case.id,
        "status": case.status.value,
        "customer_id": case.customer_id,
        "transaction_count": len(case.transaction_ids),
        "created_at": case.created_at.isoformat(),
    }


@tool(composable=True, description="SAR vakasını MASAK'a dosyalar.")
async def file_sar_report(
    case_id: str,
    approver_id: str,
    narrative: str,
    ctx: Any = None,
) -> dict:
    """File a SAR case with MASAK.

    Args:
        case_id: SAR case ID
        approver_id: ID of approving compliance officer
        narrative: Detailed narrative for filing
        ctx: ToolExecutionContext (injected)

    Returns:
        Filing result
    """
    from auraos.fintech.sar import SARCaseManager

    if ctx is None:
        return {"error": "Context required"}

    manager = ctx.get_service(SARCaseManager)
    result = await manager.approve_and_file(case_id, approver_id, narrative)

    return {
        "success": result.success,
        "case_id": result.case_id,
        "filing_reference": result.filing_reference,
        "filed_at": result.filed_at.isoformat() if result.filed_at else None,
        "error": result.error,
    }


@tool(description="Müşteri için kapsamlı AML risk değerlendirmesi yapar.")
async def comprehensive_aml_check(
    customer_name: str,
    tc_kimlik: str,
    birth_date: str | None = None,
) -> dict:
    """Perform comprehensive AML check combining multiple data sources.

    This is a standalone tool that doesn't require context services.
    For production, use individual tools with proper service injection.

    Args:
        customer_name: Customer full name
        tc_kimlik: Turkish national ID
        birth_date: Date of birth (YYYY-MM-DD)

    Returns:
        Comprehensive AML risk assessment
    """
    from auraos.integrations.masak import MASAKStubClient
    from auraos.integrations.kkb import KKBStubClient

    masak = MASAKStubClient()
    kkb = KKBStubClient()

    bd = date.fromisoformat(birth_date) if birth_date else None

    sanctions = await masak.screen_sanctions(customer_name, bd, tc_kimlik)
    pep = await masak.screen_pep(customer_name)
    credit_score = await kkb.get_credit_score(tc_kimlik)

    risk_factors = []
    risk_score = 0

    if sanctions:
        risk_factors.append(f"sanctions_match:{len(sanctions)}")
        risk_score += 50

    if pep:
        risk_factors.append(f"pep_match:{len(pep)}")
        risk_score += 30

    if credit_score.value < 1300:
        risk_factors.append("low_credit_score")
        risk_score += 10

    if risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "customer_name": customer_name,
        "tc_kimlik": tc_kimlik,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "sanctions_matches": len(sanctions),
        "pep_matches": len(pep),
        "credit_score": credit_score.value,
        "credit_risk_class": credit_score.risk_class.value,
        "assessment_date": datetime.now().isoformat(),
        "recommendation": "proceed" if risk_level == "low" else "manual_review" if risk_level == "medium" else "escalate",
    }
