# Upsonic Framework Analizi — AuraOS Karşılaştırması

> **Kaynak:** https://docs.upsonic.ai/ (Mayıs 2026)
> **Amaç:** Upsonic'in sunduğu yetenekleri analiz etmek, AuraOS'ta var olan / olmayan özellikleri belirlemek.
> **Son güncelleme:** v0.4.0 — Eksik özellikler eklendi (Faz 1-8 tamamlandı)

---

## 1. Genel Mimari Karşılaştırma

| Katman | Upsonic | AuraOS v0.4 | Durum |
|--------|---------|-------------|-------|
| Agent primitifi | `Agent`, `AutonomousAgent` | `Agent`, `AutonomousAgent` | ✅ Var |
| Task abstraction | `Task` (description, context, tools, response_format) | `Task` (description, context, tools, response_format, images, system_prompt) | ✅ Var |
| Agent kimliği | role, goal, instructions | role, goal, instructions | ✅ Var |
| Structured Output | Pydantic response_format | Pydantic response_format + JSON code fence parse | ✅ Var |
| Thinking / Reasoning | Extended thinking + reflection | Extended thinking + reflection (critique→improve) | ✅ Var |
| LLM soyutlama | `Model` sınıfı, 27+ provider | `BaseLLM`, 6 provider (Anthropic, OpenAI, Gemini, Groq, Ollama + streaming) | ✅ Var (daha az provider) |
| Tool sistemi | `@tool` decorator + ToolKit + MCP + KnowledgeBase | `@tool` decorator + ToolRegistry + sub-agent tool + agent router | ⚠️ Kısmi (MCP yok) |
| Memory | 3 tip + 5 backend | Session-based (InMemory + Redis + SQLite) | ⚠️ Kısmi (summary/user_analysis yok) |
| RAG / KnowledgeBase | 8 vector DB, 10+ loader, 8 splitter | ChromaDB + hash embedding + 7 loader + 4 splitter | ✅ Büyük ölçüde var |
| Multi-Agent | Team (sequential, coordinate, route) | Team (sequential, coordinate, route) | ✅ Var |
| Workflow | Yok (Team ile dolaylı) | WorkflowExecutor (DAG) | ✅ Biz ilerideyiz |
| HITL | User confirmation, durable execution, user input | Tool approval callback | ⚠️ Kısmi |
| Safety Engine | PII, financial, medical + anonymize/block/replace | PII + financial + anonymize/de-anonymize + Policy system (block/anonymize/replace/log/raise) | ✅ Büyük ölçüde var |
| Observability | OpenTelemetry + span hierarchy | CostTracker + Metrics + AuditLog + Tracer | ⚠️ OTel export yok |
| OCR | 6 engine, unified pipeline | Pytesseract + Pillow | ⚠️ Kısmi |
| Skills | Paketlenmiş domain bilgisi | Yok | ❌ Yok |
| Deployment | FastAPI, Django, Telegram, Slack, WhatsApp | CLI (typer) | ❌ Yok |

---

## 2. v0.4'te Eklenen Özellikler

### 2.1 Enhanced Task + Agent Identity (Faz 1) ✅

**Task yeni parametreleri:**
```python
Task(
    description="Görevi açıkla",
    context={"key": "value"},
    tools=[my_tool],                    # Per-task tool override
    response_format=MyPydanticModel,    # Structured output
    images=["image.png"],               # Multimodal input
    system_prompt="Özel system prompt", # Per-task system prompt
)
```

**Agent kimlik parametreleri:**
```python
Agent(
    name="Finans Uzmanı",
    role="Kıdemli finans analisti",
    goal="Müşteri sorularını cevaplayın",
    instructions="Türkçe yanıt ver, kısa ol",
)
```

### 2.2 Structured Output (Faz 2) ✅

```python
from pydantic import BaseModel

class CreditDecision(BaseModel):
    approved: bool
    reason: str
    risk_score: float

task = Task(
    description="Kredi başvurusunu değerlendir",
    response_format=CreditDecision,
)
result = agent.run(task)
print(result.parsed)  # CreditDecision(approved=True, reason="...", risk_score=0.85)
```

- JSON code fence içinden otomatik parse
- Parse başarısız olursa `parsed=None`, `output` ham metin kalır (graceful fallback)

### 2.3 Thinking / Reasoning + Reflection (Faz 3) ✅

```python
agent = Agent(
    name="Analist",
    thinking_enabled=True,       # Extended thinking (Anthropic/Gemini)
    thinking_budget=10000,       # Düşünme token bütçesi
    reflection=True,             # Self-critique mekanizması
)
```

Reflection akışı:
1. İlk cevabı al
2. "Bu cevabı eleştir, eksik/hatalı noktaları belirt" → critique
3. "Eleştriye göre cevabını iyileştir" → improved answer
4. İyileştirilmiş cevap final output olur

Hem `run()` hem `arun()` destekler.

### 2.4 Anonymize / De-anonymize (Faz 4) ✅

```python
from auraos import Guardrails, Anonymizer

guardrails = Guardrails(pii_anonymize=True)

# Input: "TC: 12345678901, mail: user@test.com"
# → LLM'e gönderilen: "TC: <TC_KIMLIK_1>, mail: <EMAIL_1>"
# → LLM yanıtında: "<TC_KIMLIK_1> için işlem yapıldı"
# → Kullanıcıya dönen: "12345678901 için işlem yapıldı"
```

- `[REDACTED]` yerine benzersiz token'lar → LLM bağlamı korur
- Aynı PII değeri her zaman aynı token'a eşlenir
- Agent `run()`/`arun()` içinde otomatik entegre

### 2.5 Policy System (Faz 5) ✅

```python
from auraos.security.policy import (
    Policy, PolicyAction, PolicyRule,
    pii_policy, financial_data_policy, prompt_injection_policy,
)

# Hazır policy'ler
pii = pii_policy(action=PolicyAction.ANONYMIZE)
fin = financial_data_policy(action=PolicyAction.REPLACE)
inj = prompt_injection_policy()  # BLOCK

# Özel policy
custom = Policy(name="custom", rules=[
    PolicyRule(
        name="secret_keyword",
        pattern=re.compile(r"GİZLİ"),
        action=PolicyAction.BLOCK,
    ),
])

result = pii.apply("TC: 12345678901", anonymizer=my_anonymizer)
# result.ok, result.text, result.hits, result.blocked
```

**Policy aksiyonları:** BLOCK, ANONYMIZE, REPLACE, LOG, RAISE

**Financial data pattern'leri:**
- IBAN, kredi kartı
- Hesap bakiyesi: `1.500,00 TL`, `$500`
- Maaş/gelir bilgisi

### 2.6 SQLite SessionStore (Faz 6) ✅

```python
from auraos import SessionManager, SQLiteSessionStore

store = SQLiteSessionStore(
    db_path="auraos_sessions.db",
    ttl_seconds=86400,  # 24 saat
)
sm = SessionManager(store=store)

# Session'lar process restart'larında bile korunur
session = sm.get_or_create("user_123")
session.add_message("user", "Merhaba")
sm.save(session)

# TTL geçen session'ları temizle
store.cleanup_expired()
```

### 2.7 Document Loaders (Faz 7) ✅

```python
from auraos import KnowledgeBase, get_loader

kb = KnowledgeBase()

# Otomatik loader seçimi
kb.add_file("rapor.pdf")
kb.add_file("veriler.csv")
kb.add_file("notlar.md")
kb.add_file("config.json")

# Manuel loader
from auraos import TextLoader
kb.add_file("ozel.dat", loader=TextLoader())
```

**Desteklenen formatlar:**
| Format | Loader | Bağımlılık |
|--------|--------|------------|
| .txt | TextLoader | stdlib |
| .md | MarkdownLoader | stdlib |
| .csv | CSVLoader | stdlib |
| .json | JSONLoader | stdlib |
| .pdf | PDFLoader | `pdfplumber` (opsiyonel) |
| .docx | DOCXLoader | `python-docx` (opsiyonel) |
| .html | HTMLLoader | `beautifulsoup4` (opsiyonel) |

### 2.8 Text Splitters (Faz 8) ✅

```python
from auraos import RecursiveSplitter, MarkdownSplitter, SentenceSplitter, FixedSplitter

# KnowledgeBase ile kullanım
kb = KnowledgeBase(splitter=RecursiveSplitter(chunk_size=500, overlap=50))
kb.add("Uzun metin...")

# Veya inline
kb.add("Başka metin", splitter=SentenceSplitter(max_sentences=10))
```

| Splitter | Açıklama |
|----------|----------|
| RecursiveSplitter | Paragraf → cümle → kelime sınırlarından böler |
| MarkdownSplitter | Başlık (#, ##, ###) sınırlarını kullanır |
| SentenceSplitter | Cümle bazlı bölme (Türkçe desteği) |
| FixedSplitter | Sabit karakter sayısı (backward compat) |

---

## 3. Hâlâ Eksik Olan Özellikler (Gelecek Fazlar)

### Yüksek Öncelik
| Özellik | Açıklama |
|---------|----------|
| **Durable Execution** | Agent run state checkpoint + resume |
| **User Input HITL** | Agent'ın kullanıcıdan alan istemesi |
| **FastAPI Integration** | REST API wrapper |
| **MCP Client** | External MCP server bağlantısı |

### Orta Öncelik
| Özellik | Açıklama |
|---------|----------|
| **OpenTelemetry Export** | Span-based tracing → Jaeger/Grafana |
| **Summary Memory** | LLM ile otomatik özet oluşturma |
| **User Analysis Memory** | Kullanıcı profil analizi |
| **Compression Strategy** | Context sıkıştırma |

### Düşük Öncelik
| Özellik | Açıklama |
|---------|----------|
| **Skills System** | Paketlenmiş domain bilgisi |
| **OCR Pipeline** | Multi-engine orchestration |
| **MCP Server** | Agent'ı MCP server olarak açma |
| **Messaging Channels** | Telegram, Slack, WhatsApp botu |

---

## 4. AuraOS'un Benzersiz Güçlü Yanları

Bu özellikler Upsonic'te yok ve AuraOS'un enterprise değer önerisi:

| Özellik | Açıklama |
|---------|----------|
| **Workflow Engine** | DAG tabanlı WorkflowExecutor — koşullu dallanma, paralel, onay düğümleri |
| **Compliance** | MASAK, KKB, SAR entegrasyonları — fintech'e özel |
| **Circuit Breaker** | Resilience pattern — otomatik devre kesici |
| **Idempotency** | Tool idempotency store — tekrar güvenliği |
| **RBAC** | Role-based access control — yetkilendirme |
| **Audit Logger** | Tamper-proof hash chain — denetim izi |
| **Rate Limiting** | Token bucket + scope-based — API koruması |

---

## 5. Sonuç

**v0.4 ile kapanan boşluklar:** Task abstraction, structured output, agent kimliği, thinking/reflection, anonymize/de-anonymize, policy sistemi, SQLite session, document loaders, text splitters.

**Kalan boşluklar:** Durable execution, user input HITL, FastAPI, MCP, OpenTelemetry, summary memory, skills.

**Strateji:** AuraOS artık Upsonic'in agent kalitesi özelliklerinin büyük bölümünü karşılıyor. Sonraki adım deployment (FastAPI) ve production durability (durable execution, MCP) üzerine yoğunlaşmak.
