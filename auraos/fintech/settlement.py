"""
Settlement (mutabakat) tool'ları.
"""
from __future__ import annotations
from typing import Any

from auraos.tools.decorator import tool


@tool
def reconcile_transactions(
    bank_records: list, internal_records: list, key: str = "ref_no"
) -> dict:
    """
    Banka ile iç sistem kayıtlarını karşılaştırır.

    Args:
        bank_records: Banka kayıt listesi.
        internal_records: İç sistem kayıt listesi.
        key: Eşleşme anahtarı.
    """
    bank_idx = {str(r.get(key)): r for r in bank_records}
    int_idx = {str(r.get(key)): r for r in internal_records}

    matched: list[str] = []
    mismatched: list[dict] = []
    only_in_bank: list[dict] = []
    only_in_internal: list[dict] = []

    for k, b in bank_idx.items():
        if k in int_idx:
            i = int_idx[k]
            if abs(float(b.get("amount", 0)) - float(i.get("amount", 0))) < 0.01:
                matched.append(k)
            else:
                mismatched.append({"key": k, "bank": b, "internal": i})
        else:
            only_in_bank.append(b)

    for k, i in int_idx.items():
        if k not in bank_idx:
            only_in_internal.append(i)

    return {
        "matched_count": len(matched),
        "mismatched": mismatched,
        "only_in_bank": only_in_bank,
        "only_in_internal": only_in_internal,
        "fully_balanced": not (mismatched or only_in_bank or only_in_internal),
    }


@tool
def calculate_settlement_amount(
    gross: float,
    commission_rate: float = 0.025,
    fixed_fee: float = 0.50,
    bsmv_rate: float = 0.05,
) -> dict:
    """
    Net ödenecek mutabakat tutarını hesaplar.

    Args:
        gross: Brüt tutar.
        commission_rate: Komisyon oranı.
        fixed_fee: Sabit ücret.
        bsmv_rate: BSMV oranı.
    """
    commission = gross * commission_rate + fixed_fee
    bsmv = commission * bsmv_rate
    total_fee = commission + bsmv
    net = gross - total_fee
    return {
        "gross": round(gross, 2),
        "commission": round(commission, 2),
        "bsmv": round(bsmv, 2),
        "total_fee": round(total_fee, 2),
        "net": round(net, 2),
    }
