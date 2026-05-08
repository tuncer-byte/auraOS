"""
Döviz/FX tool'ları.

Online API (frankfurter.app) ile çalışır. Internet yoksa cached fallback.
"""
from __future__ import annotations
from typing import Any

import httpx

from auraos.tools.decorator import tool


_FALLBACK_RATES = {
    "USD": 32.0, "EUR": 35.0, "GBP": 41.0, "TRY": 1.0,
}


@tool
def fx_convert(amount: float, source: str, target: str) -> dict:
    """
    Bir tutarı kaynak para biriminden hedef birime çevirir.

    Args:
        amount: Çevrilecek tutar.
        source: Kaynak para birimi (ISO-3).
        target: Hedef para birimi (ISO-3).
    """
    src = source.upper()
    tgt = target.upper()
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"https://api.frankfurter.app/latest",
                params={"from": src, "to": tgt, "amount": amount},
            )
            r.raise_for_status()
            data = r.json()
            return {
                "amount": amount,
                "source": src,
                "target": tgt,
                "converted": data["rates"][tgt],
                "rate": data["rates"][tgt] / amount,
                "date": data.get("date"),
            }
    except Exception:
        rate_src = _FALLBACK_RATES.get(src, 1.0)
        rate_tgt = _FALLBACK_RATES.get(tgt, 1.0)
        converted = amount * (rate_src / rate_tgt)
        return {
            "amount": amount,
            "source": src,
            "target": tgt,
            "converted": round(converted, 4),
            "rate": round(rate_src / rate_tgt, 6),
            "fallback": True,
        }
