"""
auraOS FinTech katmanı.

Hazır tool'lar:
  - kyc: KYC/onboarding kontrolleri
  - aml: AML/CTF risk taraması
  - risk: Müşteri/işlem risk skoru
  - settlement: Mutabakat işlemleri
  - market: Piyasa verisi (yfinance)
  - fx: Döviz çevirisi
  - compliance: Periyodik uyum denetimi
  - katilim: Katılım bankacılığı (Murabaha, Kar Payı, Helal Sektör)
  - sar: SAR (Şüpheli İşlem Bildirimi) vaka yönetimi
  - compliance_tools: Gerçek zamanlı compliance tool'ları

Ayrıca hazır agent'lar:
  - OnboardingAgent
  - AMLAgent
  - SettlementAgent
  - PeriodicControlAgent

Kullanım:
    from auraos.fintech.kyc import validate_tc_kimlik
    from auraos.fintech.katilim import murabaha_calculate
    from auraos.fintech.agents import OnboardingAgent
    from auraos.fintech.sar import SARCaseManager
    from auraos.fintech.compliance_tools import check_sanctions_realtime
"""

# Lazy imports to avoid circular dependency
def __getattr__(name):
    if name == "kyc":
        from auraos.fintech import kyc
        return kyc
    elif name == "aml":
        from auraos.fintech import aml
        return aml
    elif name == "risk":
        from auraos.fintech import risk
        return risk
    elif name == "settlement":
        from auraos.fintech import settlement
        return settlement
    elif name == "market":
        from auraos.fintech import market
        return market
    elif name == "fx":
        from auraos.fintech import fx
        return fx
    elif name == "compliance":
        from auraos.fintech import compliance
        return compliance
    elif name == "katilim":
        from auraos.fintech import katilim
        return katilim
    elif name == "sar":
        from auraos.fintech import sar
        return sar
    elif name == "compliance_tools":
        from auraos.fintech import compliance_tools
        return compliance_tools
    elif name == "SARCaseManager":
        from auraos.fintech.sar import SARCaseManager
        return SARCaseManager
    elif name == "OnboardingAgent":
        from auraos.fintech.agents import OnboardingAgent
        return OnboardingAgent
    elif name == "AMLAgent":
        from auraos.fintech.agents import AMLAgent
        return AMLAgent
    elif name == "SettlementAgent":
        from auraos.fintech.agents import SettlementAgent
        return SettlementAgent
    elif name == "PeriodicControlAgent":
        from auraos.fintech.agents import PeriodicControlAgent
        return PeriodicControlAgent
    raise AttributeError(f"module 'auraos.fintech' has no attribute '{name}'")

__all__ = [
    "kyc", "aml", "risk", "settlement", "market", "fx", "compliance", "katilim",
    "sar", "compliance_tools", "SARCaseManager",
    "OnboardingAgent", "AMLAgent", "SettlementAgent", "PeriodicControlAgent",
]
