"""
YAML/env tabanlı konfigürasyon.

Dataclass tabanlı, IDE-friendly. YAML yoksa env vars'tan okur.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from auraos.exceptions import ConfigError


@dataclass
class LLMConfig:
    model: str = "gemini/gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 60.0


@dataclass
class RateLimitConfig:
    enabled: bool = True
    rpm: int = 60
    tpm: int = 60_000


@dataclass
class CacheConfig:
    enabled: bool = True
    backend: str = "memory"  # memory | redis
    redis_url: str = "redis://localhost:6379/0"
    ttl_seconds: float = 3600.0


@dataclass
class SessionConfig:
    backend: str = "memory"  # memory | redis | sqlite
    redis_url: str = "redis://localhost:6379/0"
    sqlite_path: str = "auraos_sessions.db"
    ttl_seconds: float = 3600.0
    max_messages: int = 50


@dataclass
class GuardrailConfig:
    pii_redact: bool = True
    prompt_injection_check: bool = True
    block_on_violation: bool = False


@dataclass
class AgentConfig:
    name: str = "Agent"
    max_iterations: int = 10
    tool_timeout: Optional[float] = 30.0


@dataclass
class AuraOSConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    guardrail: GuardrailConfig = field(default_factory=GuardrailConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuraOSConfig":
        def build(section_cls, payload):
            payload = payload or {}
            return section_cls(**{k: v for k, v in payload.items() if k in section_cls.__dataclass_fields__})

        return cls(
            llm=build(LLMConfig, data.get("llm")),
            rate_limit=build(RateLimitConfig, data.get("rate_limit")),
            cache=build(CacheConfig, data.get("cache")),
            session=build(SessionConfig, data.get("session")),
            guardrail=build(GuardrailConfig, data.get("guardrail")),
            agent=build(AgentConfig, data.get("agent")),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AuraOSConfig":
        try:
            import yaml  # type: ignore
        except ImportError:
            raise ConfigError("YAML config için PyYAML gerekli: pip install pyyaml")
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Config bulunamadı: {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls.from_dict(data)

    @classmethod
    def from_env(cls) -> "AuraOSConfig":
        cfg = cls()
        if model := os.getenv("AURAOS_MODEL"):
            cfg.llm.model = model
        if temp := os.getenv("AURAOS_TEMPERATURE"):
            cfg.llm.temperature = float(temp)
        if rpm := os.getenv("AURAOS_RPM"):
            cfg.rate_limit.rpm = int(rpm)
        if backend := os.getenv("AURAOS_CACHE_BACKEND"):
            cfg.cache.backend = backend
        if backend := os.getenv("AURAOS_SESSION_BACKEND"):
            cfg.session.backend = backend
        if redis_url := os.getenv("AURAOS_REDIS_URL"):
            cfg.cache.redis_url = redis_url
            cfg.session.redis_url = redis_url
        return cfg

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "AuraOSConfig":
        """YAML varsa kullan, yoksa env, yoksa default."""
        if path and Path(path).exists():
            return cls.from_yaml(path)
        default_yaml = Path("auraos.yaml")
        if default_yaml.exists():
            return cls.from_yaml(default_yaml)
        return cls.from_env()
