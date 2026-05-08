"""
Risk skorlama tool'ları.
"""
from __future__ import annotations
from typing import Any

from auraos.tools.decorator import tool


@tool
def transaction_risk_score(
    amount: float,
    currency: str = "TRY",
    is_cross_border: bool = False,
    customer_age_days: int = 365,
    is_first_to_counterparty: bool = False,
) -> dict:
    """
    Tek işlem için risk skoru (0-100).

    Args:
        amount: İşlem tutarı.
        currency: Para birimi (ISO-3).
        is_cross_border: Sınır ötesi mi.
        customer_age_days: Müşterinin sistemdeki gün sayısı.
        is_first_to_counterparty: Bu karşı tarafa ilk işlem mi.
    """
    score = 0
    if amount >= 100_000: score += 35
    elif amount >= 25_000: score += 20
    elif amount >= 10_000: score += 10

    if currency.upper() not in {"TRY", "EUR", "USD", "GBP"}:
        score += 15

    if is_cross_border:
        score += 20

    if customer_age_days < 30:
        score += 25
    elif customer_age_days < 90:
        score += 10

    if is_first_to_counterparty:
        score += 10

    score = min(100, score)
    if score >= 70:
        band = "HIGH"
    elif score >= 40:
        band = "MEDIUM"
    else:
        band = "LOW"

    return {"score": score, "band": band}


@tool
def merchant_risk_score(
    mcc: str,
    monthly_volume: float,
    chargeback_ratio: float,
    months_in_business: int,
) -> dict:
    """
    Merchant (üye iş yeri) için risk skoru.

    Args:
        mcc: Merchant Category Code.
        monthly_volume: Aylık ciro (TL).
        chargeback_ratio: Geri ibraz oranı (0-1).
        months_in_business: Faaliyet süresi (ay).
    """
    HIGH_RISK_MCC = {"7995", "5967", "6051", "5933", "4829"}
    score = 0
    if mcc in HIGH_RISK_MCC: score += 40
    if chargeback_ratio > 0.01: score += 30
    if chargeback_ratio > 0.02: score += 20
    if months_in_business < 6: score += 20
    if monthly_volume > 1_000_000: score += 10

    score = min(100, score)
    band = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"
    return {"score": score, "band": band, "mcc": mcc}
