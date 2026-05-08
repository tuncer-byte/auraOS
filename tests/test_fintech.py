"""KYC ve AML tool testleri."""
from auraos.fintech.kyc import validate_tc_kimlik, validate_iban, calculate_age
from auraos.fintech.aml import detect_structuring, aml_assessment


def test_tc_invalid_length():
    r = validate_tc_kimlik("123")
    assert r["valid"] is False


def test_tc_starts_with_zero():
    r = validate_tc_kimlik("01234567890")
    assert r["valid"] is False


def test_iban_format():
    r = validate_iban("TR")
    assert r["valid"] is False


def test_calculate_age():
    r = calculate_age("2000-01-01")
    assert r["age"] >= 25
    assert r["is_adult"] is True


def test_structuring_detected():
    txs = [
        {"amount": 9500, "date": "2026-04-01"},
        {"amount": 9700, "date": "2026-04-02"},
        {"amount": 9800, "date": "2026-04-03"},
    ]
    r = detect_structuring(txs, threshold=10000)
    assert r["structuring"] is True
    assert r["near_threshold_count"] == 3


def test_aml_pass_path():
    r = aml_assessment("Temiz Müşteri", [], country="TR")
    assert r["decision"] == "PASS"
    assert r["score"] < 20


def test_aml_high_risk_country():
    r = aml_assessment("X", [], country="IR")
    assert r["score"] >= 25
