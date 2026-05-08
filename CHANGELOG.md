# Changelog

Tüm önemli değişiklikler bu dosyaya kayıt edilir. [Keep a Changelog](https://keepachangelog.com/) ve [Semantic Versioning](https://semver.org/) kurallarına uyulur.

## [0.2.0] — 2026-05-08

### Eklendi (Kurumsal sınıf)

**Observability**
- `AuditLog` — append-only JSONL + SHA-256 hash zinciri, `verify()` ile manipülasyon tespiti
- `MetricsRegistry` + Prometheus exposition (`Counter`, `Gauge`, `Histogram`, `Timer`)
- `CostTracker` — model/session bazında token + USD; `DEFAULT_PRICING` (Gemini, GPT, Claude)
- `JsonFormatter` + `configure_json_logging()` — yapılandırılmış JSON loglar
- Correlation ID / Session ID / Tenant ID context vars (`contextvars`)

**Güvenilirlik**
- `CircuitBreaker` (closed → open → half_open) — LLM ve servis arızalarında hızlı izole
- `IdempotencyStore` + `make_idempotency_key()` — kritik tool çağrılarında tekrar koruması
- `RateLimiter` (token bucket, sync + async) — provider kotası koruması
- `RetryPolicy` — exponential backoff + jitter

**Güvenlik**
- `Principal` + `RBACGuard` — tool seviyesinde rol tabanlı yetkilendirme
- `Guardrails` — TR/EN PII redact, prompt injection tespiti, IO kontrolü
- `@tool(requires_approval=True, required_roles=..., idempotent=True)` — bayraklar

**Çekirdek**
- `Agent.arun()`, `Agent.astream()` — async + token streaming
- `SessionManager` (InMemory + Redis backend) — kalıcı konuşma hafızası
- `AuraOSConfig` — YAML / dict / env'den merkezi yapılandırma
- Pydantic destekli tool argüman validasyonu (tip coercion, bilinmeyen alan strip)
- 4 embedding provider: Hash / OpenAI / Gemini / SentenceTransformer
- 2-katmanlı cache: `InMemoryCache` + `RedisCache`

**Hata hiyerarşisi**
- `AuraOSError` kökü, alt sınıflar: `LLMError`, `ToolError`, `ToolApprovalRequired`, `ToolApprovalDenied`, `ToolValidationError`, `ToolTimeoutError`, `MaxIterationsExceeded`, `SessionError`, `GuardrailError`, `PromptInjectionError`, `RateLimitExceededError`, `CircuitOpenError`, `AuthorizationError`

### Değişti
- `Agent` artık opsiyonel olarak: `audit_log`, `cost_tracker`, `circuit_breaker`, `metrics`, `actor`, `session_manager`, `guardrails`, `rate_limiter`, `cache`, `approval_callback`, `tool_timeout` parametreleri alır
- `ToolRegistry` artık `rbac_guard` ve `idempotency_store` enjekte edilebilir
- LLM çağrıları cost tracker'a bağlandı; metric'ler her çağrıda güncellenir

### Test
- 67 birim test (45 → 67) — audit, cost, metrics, circuit breaker, idempotency, RBAC, guardrails, sessions, async, streaming
