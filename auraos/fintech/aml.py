"""
AML (Anti-Money Laundering) tool'ları.

İçerir:
  - PEP/yaptırım listesi taraması (mock)
  - İşlem örüntü tespiti
  - Yapı bozma (structuring) sezgileri
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

from auraos.tools.decorator import tool


# Demo amaçlı küçük bir örnek liste; üretimde MASAK/OFAC API'lerine bağlanır.
_SANCTIONS_LIST = {
    "ahmet kötü": "OFAC SDN",
    "kara para a.ş.": "AB Sanctions",
    "fictional shell ltd": "OFAC SDN",
}

_PEP_LIST = {
    "siyasi figür demo": "Türkiye - Eski Bakan",
}


@tool
def screen_sanctions(name: str) -> dict:
    """
    İsmi yaptırım listelerine karşı tarar.

    Args:
        name: Tam ad veya unvan.
    """
    n = name.strip().lower()
    hit = _SANCTIONS_LIST.get(n)
    return {
        "name": name,
        "match": hit is not None,
        "list": hit,
    }


@tool
def screen_pep(name: str) -> dict:
    """
    PEP (Politically Exposed Person) listesi taraması.

    Args:
        name: Tam ad.
    """
    n = name.strip().lower()
    hit = _PEP_LIST.get(n)
    return {"name": name, "is_pep": hit is not None, "details": hit}


@tool
def detect_structuring(
    transactions: list, threshold: float = 10000.0, window_days: int = 7
) -> dict:
    """
    Yapı bozma (structuring) örüntüsü tespit eder: eşik altı çoklu işlemler.

    Args:
        transactions: [{amount, date}] listesi.
        threshold: Bildirim eşiği (TL).
        window_days: Pencere büyüklüğü (gün).
    """
    if not transactions:
        return {"structuring": False, "reason": "no transactions"}

    near_threshold = [
        t for t in transactions
        if 0.7 * threshold <= float(t.get("amount", 0)) < threshold
    ]
    suspect = len(near_threshold) >= 3

    total = sum(float(t.get("amount", 0)) for t in near_threshold)
    return {
        "structuring": suspect,
        "near_threshold_count": len(near_threshold),
        "near_threshold_total": total,
        "exceeds_threshold_via_split": total > threshold and suspect,
    }


@tool
def velocity_check(transactions: list, max_per_day: int = 10) -> dict:
    """
    İşlem yoğunluğu/velocity kontrolü.

    Args:
        transactions: İşlem listesi.
        max_per_day: Günlük maksimum kabul edilebilir işlem sayısı.
    """
    by_day: dict[str, int] = {}
    for t in transactions:
        d = str(t.get("date", ""))[:10]
        by_day[d] = by_day.get(d, 0) + 1
    breaches = {d: c for d, c in by_day.items() if c > max_per_day}
    return {
        "max_per_day": max_per_day,
        "breach_days": breaches,
        "alert": bool(breaches),
    }


@tool
def aml_assessment(
    name: str,
    transactions: list,
    country: str = "TR",
) -> dict:
    """
    Müşteri için bütüncül AML değerlendirmesi.

    Args:
        name: Müşteri adı.
        transactions: İşlem listesi.
        country: Müşteri ülkesi (ISO-2).
    """
    sanctions = screen_sanctions(name)
    pep = screen_pep(name)
    structuring = detect_structuring(transactions)
    velocity = velocity_check(transactions)

    HIGH_RISK_COUNTRIES = {"IR", "KP", "MM", "RU", "SY"}
    high_risk_country = country.upper() in HIGH_RISK_COUNTRIES

    score = 0
    if sanctions["match"]: score += 100
    if pep["is_pep"]: score += 40
    if structuring["structuring"]: score += 30
    if velocity["alert"]: score += 20
    if high_risk_country: score += 25

    if score >= 100:
        decision = "BLOCK"
    elif score >= 50:
        decision = "ENHANCED_DUE_DILIGENCE"
    elif score >= 20:
        decision = "MONITOR"
    else:
        decision = "PASS"

    return {
        "name": name,
        "country": country,
        "score": score,
        "decision": decision,
        "components": {
            "sanctions": sanctions,
            "pep": pep,
            "structuring": structuring,
            "velocity": velocity,
            "high_risk_country": high_risk_country,
        },
    }
