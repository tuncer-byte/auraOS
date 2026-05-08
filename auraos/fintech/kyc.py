"""
KYC (Know Your Customer) tool'ları.

Türkiye odaklı: TC kimlik no doğrulama (algoritmik), MERSIS, vergi no
formatı kontrolleri ve müşteri profili özetleme.
"""
from __future__ import annotations
import re
from datetime import date, datetime
from typing import Any

from auraos.tools.decorator import tool


@tool
def validate_tc_kimlik(tc_no: str) -> dict:
    """
    TC kimlik numarasını algoritmik olarak doğrular.

    Args:
        tc_no: 11 haneli TC kimlik numarası.
    """
    s = re.sub(r"\D", "", tc_no)
    if len(s) != 11 or s[0] == "0":
        return {"valid": False, "reason": "11 hane olmalı, ilk hane 0 olamaz"}

    digits = [int(c) for c in s]
    odd_sum = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    even_sum = digits[1] + digits[3] + digits[5] + digits[7]
    d10 = (odd_sum * 7 - even_sum) % 10
    d11 = (odd_sum + even_sum + digits[9]) % 10

    valid = (d10 == digits[9]) and (d11 == digits[10])
    return {
        "valid": bool(valid),
        "tc_no": s,
        "reason": "ok" if valid else "checksum hatalı",
    }


@tool
def validate_vkn(vkn: str) -> dict:
    """
    Vergi kimlik numarasını (VKN) format olarak doğrular.

    Args:
        vkn: 10 haneli vergi numarası.
    """
    s = re.sub(r"\D", "", vkn)
    if len(s) != 10:
        return {"valid": False, "reason": "10 hane olmalı"}
    return {"valid": True, "vkn": s}


@tool
def validate_iban(iban: str) -> dict:
    """
    IBAN'ı mod-97 algoritmasıyla doğrular (TR, EU formatları).

    Args:
        iban: IBAN string'i.
    """
    s = re.sub(r"\s", "", iban).upper()
    if len(s) < 15 or len(s) > 34:
        return {"valid": False, "reason": "uzunluk hatalı"}

    rearranged = s[4:] + s[:4]
    numeric = "".join(
        str(ord(c) - 55) if c.isalpha() else c for c in rearranged
    )
    try:
        valid = int(numeric) % 97 == 1
    except ValueError:
        return {"valid": False, "reason": "format hatalı"}
    return {"valid": valid, "iban": s, "country": s[:2]}


@tool
def calculate_age(birth_date: str) -> dict:
    """
    Doğum tarihinden yaşı hesaplar (YYYY-MM-DD).

    Args:
        birth_date: ISO formatında doğum tarihi.
    """
    bd = datetime.fromisoformat(birth_date).date()
    today = date.today()
    age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    return {"age": age, "is_adult": age >= 18}


@tool
def kyc_summary(
    full_name: str,
    tc_no: str,
    birth_date: str,
    address: str,
    profession: str = "",
) -> dict:
    """
    Müşteri için kompozit KYC özeti üretir; tüm alt kontrolleri çalıştırır.

    Args:
        full_name: Ad-soyad.
        tc_no: TC kimlik numarası.
        birth_date: YYYY-MM-DD doğum tarihi.
        address: Açık adres.
        profession: Meslek.
    """
    tc_check = validate_tc_kimlik(tc_no)
    age_check = calculate_age(birth_date)

    flags: list[str] = []
    if not tc_check["valid"]:
        flags.append("invalid_tc")
    if not age_check["is_adult"]:
        flags.append("under_18")
    if len(address.strip()) < 10:
        flags.append("address_too_short")

    return {
        "full_name": full_name,
        "tc": tc_check,
        "age": age_check,
        "profession": profession or "belirtilmedi",
        "address_ok": len(address.strip()) >= 10,
        "flags": flags,
        "decision": "REJECT" if flags else "PASS",
    }
