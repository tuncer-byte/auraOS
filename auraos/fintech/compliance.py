"""
Periyodik uyum/compliance tool'ları.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any

from auraos.tools.decorator import tool


@tool
def kvkk_data_retention_check(record_created: str, retention_years: int = 10) -> dict:
    """
    KVKK için saklama süresi kontrolü.

    Args:
        record_created: Kayıt oluşturulma tarihi (YYYY-MM-DD).
        retention_years: Yasal saklama süresi (yıl).
    """
    created = datetime.fromisoformat(record_created).date()
    expiry = created.replace(year=created.year + retention_years)
    today = date.today()
    return {
        "created": str(created),
        "expires_on": str(expiry),
        "expired": today > expiry,
        "days_remaining": (expiry - today).days,
    }


@tool
def periodic_review_due(last_review: str, period_months: int = 12) -> dict:
    """
    Müşteri için periyodik gözden geçirme zamanı geldi mi.

    Args:
        last_review: Son gözden geçirme tarihi (YYYY-MM-DD).
        period_months: Periyot uzunluğu (ay).
    """
    last = datetime.fromisoformat(last_review).date()
    due_year = last.year + (last.month + period_months - 1) // 12
    due_month = ((last.month + period_months - 1) % 12) + 1
    due = date(due_year, due_month, min(last.day, 28))
    today = date.today()
    return {
        "last_review": str(last),
        "due_on": str(due),
        "is_due": today >= due,
        "days_overdue": max(0, (today - due).days),
    }
