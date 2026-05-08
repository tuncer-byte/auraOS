"""
Piyasa verisi tool'ları (yfinance opsiyonel).
"""
from __future__ import annotations
from typing import Any

from auraos.tools.decorator import tool


@tool
def get_stock_quote(symbol: str) -> dict:
    """
    Verilen sembol için anlık fiyat bilgisini döner (yfinance).

    Args:
        symbol: Hisse sembolü, örn: 'AAPL', 'THYAO.IS'.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance yüklü değil: pip install yfinance"}

    t = yf.Ticker(symbol)
    info = t.fast_info if hasattr(t, "fast_info") else {}
    return {
        "symbol": symbol,
        "last_price": getattr(info, "last_price", None),
        "currency": getattr(info, "currency", None),
        "day_high": getattr(info, "day_high", None),
        "day_low": getattr(info, "day_low", None),
    }


@tool
def get_stock_history(symbol: str, period: str = "1mo") -> dict:
    """
    Geçmiş fiyat serisi.

    Args:
        symbol: Sembol.
        period: '1d', '5d', '1mo', '3mo', '1y', 'max' vb.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance yüklü değil"}

    df = yf.Ticker(symbol).history(period=period)
    return {
        "symbol": symbol,
        "period": period,
        "rows": len(df),
        "first": df.iloc[0].to_dict() if len(df) else None,
        "last": df.iloc[-1].to_dict() if len(df) else None,
        "max_close": float(df["Close"].max()) if len(df) else None,
        "min_close": float(df["Close"].min()) if len(df) else None,
    }
