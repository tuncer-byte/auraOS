"""
auraOS hazır FinTech agent'ları.

Bunlar `Agent` üzerine ince sarmalayıcılardır; ilgili tool seti ve
finans-spesifik sistem prompt'u ile gelir.
"""
from __future__ import annotations
from typing import Optional

from auraos.core.agent import Agent
from auraos.tools.registry import ToolRegistry
from auraos.fintech import kyc, aml, risk, settlement, compliance, fx


class OnboardingAgent(Agent):
    """KYC + sanctions taraması + ilk risk değerlendirmesi."""

    def __init__(self, model: str = "anthropic/claude-sonnet-4-5", **kwargs):
        registry = ToolRegistry()
        for t in [
            kyc.validate_tc_kimlik, kyc.validate_vkn, kyc.validate_iban,
            kyc.calculate_age, kyc.kyc_summary,
            aml.screen_sanctions, aml.screen_pep,
        ]:
            registry.register(t)

        super().__init__(
            name="OnboardingAgent",
            model=model,
            tools=registry,
            system_prompt=(
                "Sen merchant/müşteri onboarding ajanısın. KYC tool'larını "
                "kullanarak kimlik, vergi, IBAN, yaş kontrollerini yap. "
                "Yaptırım ve PEP taramasını ihmal etme. Sonuçta net karar üret: "
                "PASS / REVIEW / REJECT. Her karara gerekçe yaz."
            ),
            **kwargs,
        )


class AMLAgent(Agent):
    """Anti-Money Laundering ve şüpheli işlem analizi."""

    def __init__(self, model: str = "anthropic/claude-sonnet-4-5", **kwargs):
        registry = ToolRegistry()
        for t in [
            aml.screen_sanctions, aml.screen_pep,
            aml.detect_structuring, aml.velocity_check, aml.aml_assessment,
            risk.transaction_risk_score, risk.merchant_risk_score,
        ]:
            registry.register(t)

        super().__init__(
            name="AMLAgent",
            model=model,
            tools=registry,
            system_prompt=(
                "Sen AML uzmanı bir ajansın. Müşteri ve işlem verilerinde "
                "structuring, anormal hız, yaptırım/PEP eşleşmesi gibi sinyalleri ara. "
                "MASAK uyumu için BLOCK / EDD / MONITOR / PASS kararı üret."
            ),
            **kwargs,
        )


class SettlementAgent(Agent):
    """Mutabakat ve net ödeme hesaplama."""

    def __init__(self, model: str = "anthropic/claude-sonnet-4-5", **kwargs):
        registry = ToolRegistry()
        for t in [
            settlement.reconcile_transactions,
            settlement.calculate_settlement_amount,
            fx.fx_convert,
        ]:
            registry.register(t)

        super().__init__(
            name="SettlementAgent",
            model=model,
            tools=registry,
            system_prompt=(
                "Sen mutabakat ajanısın. Banka ve iç sistem kayıtlarını "
                "karşılaştır, farkları rapor et, net mutabakat tutarını hesapla. "
                "Açıkları ve nedenlerini net liste halinde sun."
            ),
            **kwargs,
        )


class PeriodicControlAgent(Agent):
    """KVKK/MASAK/dahili periyodik kontroller."""

    def __init__(self, model: str = "anthropic/claude-sonnet-4-5", **kwargs):
        registry = ToolRegistry()
        for t in [
            compliance.kvkk_data_retention_check,
            compliance.periodic_review_due,
            aml.aml_assessment,
        ]:
            registry.register(t)

        super().__init__(
            name="PeriodicControlAgent",
            model=model,
            tools=registry,
            system_prompt=(
                "Sen periyodik denetim ajanısın. Müşteri portföyünde "
                "KVKK saklama süresi, AML yenileme, müşteri review tarihleri "
                "gibi kontrolleri çalıştır ve aksiyon listesi üret."
            ),
            **kwargs,
        )
