"""
02 - FinTech tool'ları: KYC + AML birlikte.
"""
from auraos.fintech.kyc import (
    validate_tc_kimlik, validate_iban, kyc_summary,
)
from auraos.fintech.aml import aml_assessment


def main():
    # 1) TC ve IBAN doğrulama
    print("TC:", validate_tc_kimlik("12345678901"))
    print("IBAN:", validate_iban("TR320010009999901234567890"))

    # 2) KYC özeti
    summary = kyc_summary(
        full_name="Mehmet Demo",
        tc_no="12345678901",
        birth_date="1990-05-15",
        address="Atatürk Cd. No:1 Kadıköy/İstanbul",
        profession="Yazılım Mühendisi",
    )
    print("\nKYC özeti:", summary)

    # 3) AML değerlendirmesi
    transactions = [
        {"amount": 9500, "date": "2026-04-01"},
        {"amount": 9800, "date": "2026-04-02"},
        {"amount": 9700, "date": "2026-04-03"},
    ]
    aml = aml_assessment(
        name="Mehmet Demo",
        transactions=transactions,
        country="TR",
    )
    print("\nAML değerlendirmesi:", aml)


if __name__ == "__main__":
    main()
