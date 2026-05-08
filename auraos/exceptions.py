"""
auraOS özel istisna hiyerarşisi.

Production'da ham Exception fırlatmak yerine semantik hata sınıfları
kullanılır. Böylece kullanıcıya güvenli mesajlar dönülür, loglarda
hata türü ayrıştırılabilir, retry/fallback kararları net verilir.
"""
from __future__ import annotations
from typing import Any, Optional


class AuraOSError(Exception):
    """Tüm auraOS hatalarının kökü."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ---- LLM hataları ----
class LLMError(AuraOSError):
    """LLM provider seviyesi hata."""


class LLMConnectionError(LLMError):
    """Network / bağlantı sorunu - retry edilebilir."""


class LLMRateLimitError(LLMError):
    """Provider rate limit - retry with backoff."""

    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class LLMAuthError(LLMError):
    """API key hatalı / yetkisiz - retry edilemez."""


class LLMTimeoutError(LLMError):
    """LLM yanıt zaman aşımı."""


class LLMResponseError(LLMError):
    """Provider beklenmeyen format döndü."""


# ---- Tool hataları ----
class ToolError(AuraOSError):
    """Tool seviyesi hata."""

    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(f"[{tool_name}] {message}", **kwargs)
        self.tool_name = tool_name


class ToolNotFoundError(ToolError):
    """Çağrılan tool kayıtlı değil."""


class ToolValidationError(ToolError):
    """Tool parametre validasyonu başarısız."""


class ToolExecutionError(ToolError):
    """Tool çalışırken hata fırlattı."""


class ToolTimeoutError(ToolError):
    """Tool zaman aşımına uğradı."""

    def __init__(self, tool_name: str, timeout: float, **kwargs):
        super().__init__(tool_name, f"timeout after {timeout}s", **kwargs)
        self.timeout = timeout


class ToolApprovalRequired(ToolError):
    """Human-in-the-loop onayı gerekli."""

    def __init__(self, tool_name: str, arguments: dict[str, Any], **kwargs):
        super().__init__(tool_name, "approval required", **kwargs)
        self.arguments = arguments


class ToolApprovalDenied(ToolError):
    """Kullanıcı tool çağrısını reddetti."""


# ---- Agent hataları ----
class AgentError(AuraOSError):
    """Agent seviyesi hata."""


class MaxIterationsExceeded(AgentError):
    """Agent max_iterations'a ulaştı, sonuca varamadı."""


class AgentCancelled(AgentError):
    """Agent çalışması iptal edildi."""


# ---- Session / Memory hataları ----
class SessionError(AuraOSError):
    """Session yönetimi hatası."""


class SessionNotFoundError(SessionError):
    """İstenen session bulunamadı."""


class SessionExpiredError(SessionError):
    """Session TTL doldu."""


# ---- Rate limit / quota ----
class RateLimitExceededError(AuraOSError):
    """auraOS iç rate limit aşıldı."""

    def __init__(self, scope: str, retry_after: float, **kwargs):
        super().__init__(f"Rate limit exceeded for {scope}", **kwargs)
        self.scope = scope
        self.retry_after = retry_after


# ---- Guardrail hataları ----
class GuardrailError(AuraOSError):
    """Guardrail (PII / prompt injection / toxicity) ihlali."""


class PIIDetectedError(GuardrailError):
    """Çıktıda PII tespit edildi."""


class PromptInjectionError(GuardrailError):
    """Prompt injection denemesi tespit edildi."""


# ---- Config ----
class ConfigError(AuraOSError):
    """Konfigürasyon yükleme/validasyon hatası."""
