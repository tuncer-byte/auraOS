"""
Katılım Bankacılığı (Islamic Finance) tool'ları.

İçerir:
  - Murabaha kar hesaplama
  - Kar payı dağıtımı
  - Helal/Haram sektör taraması
  - Sukuk değerlendirme
  - Katılım fonu uygunluk kontrolü
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

from auraos.tools.decorator import tool


# Haram/şüpheli sektör kodları (MCC + NACE bazlı)
HARAM_SECTORS = {
    "5813": "İçki servisi yapan barlar",
    "5921": "Alkollü içecek satışı",
    "7995": "Kumar/Bahis",
    "5933": "Rehinci (faizli)",
    "6211": "Menkul kıymet brokerlığı (konvansiyonel)",
    "7273": "Eskort/yetişkin hizmetleri",
    "5122": "Tütün ürünleri",
}

SHUBHA_SECTORS = {  # Şüpheli - detaylı inceleme gerekir
    "5812": "Restoran (alkol servisi var mı?)",
    "5499": "Market (alkol/domuz satıyor mu?)",
    "6022": "Konvansiyonel banka",
    "6141": "Konvansiyonel kredi kuruluşu",
    "4511": "Havayolu (alkol servisi)",
}


@tool
def halal_sector_check(mcc: str, company_name: str = "") -> dict:
    """
    MCC koduna göre sektörün helal uygunluğunu kontrol eder.

    Args:
        mcc: Merchant Category Code (4 haneli).
        company_name: Firma adı (opsiyonel, ek kontrol için).
    """
    if mcc in HARAM_SECTORS:
        return {
            "mcc": mcc,
            "status": "HARAM",
            "reason": HARAM_SECTORS[mcc],
            "decision": "REJECT",
        }
    if mcc in SHUBHA_SECTORS:
        return {
            "mcc": mcc,
            "status": "SHUBHA",
            "reason": SHUBHA_SECTORS[mcc],
            "decision": "REVIEW_REQUIRED",
            "note": "Detaylı inceleme ve Danışma Kurulu görüşü gerekli",
        }
    return {
        "mcc": mcc,
        "status": "HALAL",
        "decision": "ELIGIBLE",
    }


@tool
def murabaha_calculate(
    cost_price: float,
    profit_rate: float,
    term_months: int,
    payment_type: str = "equal",
) -> dict:
    """
    Murabaha finansman hesaplaması yapar.

    Args:
        cost_price: Malın maliyet bedeli (TL).
        profit_rate: Yıllık kar oranı (örn: 0.36 = %36).
        term_months: Vade (ay).
        payment_type: "equal" (eşit taksit) veya "decreasing" (azalan).
    """
    total_profit = cost_price * profit_rate * (term_months / 12)
    sale_price = cost_price + total_profit

    if payment_type == "equal":
        monthly_payment = sale_price / term_months
        schedule = [{"month": i+1, "payment": round(monthly_payment, 2)}
                   for i in range(term_months)]
    else:
        principal_monthly = cost_price / term_months
        schedule = []
        for i in range(term_months):
            profit_portion = (total_profit / term_months) * (term_months - i) / term_months * 2
            payment = principal_monthly + profit_portion
            schedule.append({"month": i+1, "payment": round(payment, 2)})

    return {
        "cost_price": cost_price,
        "profit_rate": f"{profit_rate*100:.2f}%",
        "term_months": term_months,
        "total_profit": round(total_profit, 2),
        "sale_price": round(sale_price, 2),
        "monthly_payment": round(sale_price / term_months, 2) if payment_type == "equal" else "değişken",
        "payment_type": payment_type,
        "schedule_sample": schedule[:3] + [{"...": "..."}] + schedule[-1:] if term_months > 6 else schedule,
    }


@tool
def katilim_profit_share(
    pool_total: float,
    customer_balance: float,
    pool_profit: float,
    bank_share_ratio: float = 0.20,
) -> dict:
    """
    Katılım hesabı kar payı dağıtımı hesaplar.

    Args:
        pool_total: Havuz toplam bakiyesi.
        customer_balance: Müşteri bakiyesi.
        pool_profit: Havuzun elde ettiği toplam kar.
        bank_share_ratio: Banka payı oranı (mudarib payı).
    """
    customer_pool_share = customer_balance / pool_total
    gross_customer_profit = pool_profit * customer_pool_share
    bank_cut = gross_customer_profit * bank_share_ratio
    net_customer_profit = gross_customer_profit - bank_cut
    effective_rate = (net_customer_profit / customer_balance) * 12

    return {
        "customer_balance": customer_balance,
        "pool_share": f"{customer_pool_share*100:.4f}%",
        "gross_profit": round(gross_customer_profit, 2),
        "bank_share": round(bank_cut, 2),
        "net_profit": round(net_customer_profit, 2),
        "effective_annual_rate": f"{effective_rate*100:.2f}%",
    }


@tool
def sukuk_eligibility(
    issuer: str,
    underlying_asset: str,
    structure: str,
    amount: float,
    tenor_years: int,
) -> dict:
    """
    Sukuk (kira sertifikası) uygunluk değerlendirmesi.

    Args:
        issuer: İhraççı kurum.
        underlying_asset: Dayanak varlık açıklaması.
        structure: Sukuk yapısı (icara, mudaraba, wakala, hybrid).
        amount: İhraç tutarı.
        tenor_years: Vade (yıl).
    """
    VALID_STRUCTURES = {"icara", "mudaraba", "wakala", "musharaka", "hybrid", "istisna"}

    issues = []

    if structure.lower() not in VALID_STRUCTURES:
        issues.append(f"Bilinmeyen yapı: {structure}")

    if not underlying_asset or len(underlying_asset) < 10:
        issues.append("Dayanak varlık açıkça tanımlanmalı")

    if tenor_years > 30:
        issues.append("30 yılı aşan vadeler için özel değerlendirme gerekli")

    if "faiz" in underlying_asset.lower() or "interest" in underlying_asset.lower():
        issues.append("Dayanak varlık faiz içerikli olamaz")

    return {
        "issuer": issuer,
        "structure": structure,
        "amount": amount,
        "tenor_years": tenor_years,
        "shariah_compliant": len(issues) == 0,
        "issues": issues,
        "decision": "ELIGIBLE" if not issues else "REVIEW_REQUIRED",
        "note": "Danışma Kurulu nihai onayı gereklidir" if issues else "Ön değerlendirme olumlu",
    }


@tool
def takaful_premium(
    coverage_amount: float,
    coverage_type: str,
    age: int,
    term_years: int,
) -> dict:
    """
    Tekafül (İslami sigorta) prim hesaplaması.

    Args:
        coverage_amount: Teminat tutarı.
        coverage_type: "hayat", "saglik", "konut", "arac".
        age: Sigortalı yaşı.
        term_years: Sigorta süresi.
    """
    BASE_RATES = {
        "hayat": 0.003,
        "saglik": 0.025,
        "konut": 0.002,
        "arac": 0.035,
    }

    base_rate = BASE_RATES.get(coverage_type.lower(), 0.01)

    if coverage_type.lower() in ["hayat", "saglik"]:
        if age > 50:
            base_rate *= 1.5
        elif age > 40:
            base_rate *= 1.2

    annual_contribution = coverage_amount * base_rate
    tabarru_portion = annual_contribution * 0.70
    savings_portion = annual_contribution * 0.30

    return {
        "coverage_type": coverage_type,
        "coverage_amount": coverage_amount,
        "term_years": term_years,
        "annual_contribution": round(annual_contribution, 2),
        "tabarru_donation": round(tabarru_portion, 2),
        "savings_investment": round(savings_portion, 2),
        "total_contribution": round(annual_contribution * term_years, 2),
        "model": "Wakala-Waqf hybrid",
    }


@tool
def financing_dsr_check(
    monthly_income: float,
    existing_debts: float,
    proposed_payment: float,
    max_dsr: float = 0.50,
) -> dict:
    """
    Borç servis oranı (DSR) kontrolü - finansman uygunluğu.

    Args:
        monthly_income: Aylık net gelir.
        existing_debts: Mevcut aylık borç ödemeleri.
        proposed_payment: Önerilen finansman taksiti.
        max_dsr: Maksimum kabul edilebilir DSR (varsayılan %50).
    """
    total_debt = existing_debts + proposed_payment
    dsr = total_debt / monthly_income

    disposable = monthly_income - total_debt

    return {
        "monthly_income": monthly_income,
        "existing_debts": existing_debts,
        "proposed_payment": proposed_payment,
        "total_monthly_debt": total_debt,
        "dsr": f"{dsr*100:.1f}%",
        "max_allowed_dsr": f"{max_dsr*100:.0f}%",
        "disposable_income": round(disposable, 2),
        "eligible": dsr <= max_dsr,
        "recommendation": "APPROVE" if dsr <= max_dsr * 0.8 else "APPROVE_WITH_CONDITION" if dsr <= max_dsr else "REJECT",
    }
