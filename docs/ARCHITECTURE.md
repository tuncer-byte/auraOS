# auraOS Mimari Notları

## Tasarım İlkeleri

1. **Sade, ince çekirdek.** Her modül 100-300 satır arası, tek sorumluluk.
2. **Provider-agnostik.** LLM/memory/vector backend'leri tak-çıkar.
3. **Sandbox varsayılan açık.** Otonom agent her zaman workspace'le sınırlı.
4. **FinTech bir uzantıdır.** Çekirdek genel amaçlıdır, `auraos.fintech`
   tamamen opsiyoneldir; framework'ü başka domain'lerde kullanabilirsin.
5. **Test edilebilirlik.** `MockLLM` sayesinde hiçbir API key olmadan tüm
   davranışlar deterministik test edilebilir.

## Veri Akışı

```
User Task
   ▼
Agent
 ├── system_prompt
 ├── KnowledgeBase.search(query) → RAG context
 ├── Memory.get_recent() → konuşma geçmişi
 ├── ToolRegistry.schemas() → LLM'e tool katalogu
 └── LLM.complete(messages, tools)
        │
        ├── tool_calls → ToolRegistry.invoke() → result
        │     └── (tool builtin'leriyse Workspace/SafeShell üzerinden)
        │
        └── final content
                ▼
        Memory.add() (sürekli) + Tracer.end() + AgentResponse
```

## Sandbox Garantisi

`Workspace._resolve()` üç seviye kontrol yapar:

1. Mutlak yol reddi.
2. `Path.resolve()` ile sembolik link genişletme.
3. `relative_to(root)` ile final yolun gerçekten root altında olduğunu
   kanıtlama.

`SafeShell` ek olarak komut adını allowlist'te kontrol eder ve
"rm -rf /", "mkfs", "sudo" gibi tehlikeli desenleri ham metin üzerinde
reddeder.

## LLM Provider Sözleşmesi

Her provider `complete(messages, tools, temperature, max_tokens)` alır
ve şunu döner:

```python
LLMResponse(
    content: str,           # düz metin cevap
    tool_calls: list[dict], # [{"id", "name", "arguments"}]
    tokens_used: int,
    raw: Any,               # provider raw response (debug)
)
```

Bu sözleşme `Agent.run` tarafından provider-bağımsız tüketilir; yeni
bir sağlayıcı eklemek tek dosyalık iştir.

## Multi-Agent

| Mod | Senaryo |
|-----|---------|
| SEQUENTIAL | Onboarding → AML → Compliance hat-zinciri |
| COORDINATE | Bir koordinatör + uzman agentler; sentez ile tek cevap |
| ROUTE | Müşteri tipi/işlem türüne göre dinamik agent seçimi |

`router` parametresi callable; deterministik kural-tabanlı veya küçük
bir sınıflandırıcı modelle de karar verebilirsin.
