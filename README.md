# auraOS

> **Finansal AI Agent Framework** — Kurumsal sınıf, finans odaklı, açık kaynak Python framework'ü.

`auraOS`; otonom ve tool-driven agent mimarilerini, multi-agent koordinasyonunu, RAG bilgi tabanını, workflow engine'i, enterprise güvenlik katmanlarını ve hazır FinTech tool/agent'larını tek bir pakette sunar.

```
┌──────────────────────────────────────────────────────────────┐
│                        auraOS v0.4                           │
├──────────────────────────────────────────────────────────────┤
│  Core Agents   │  Tools & Registry  │  Memory & Sessions     │
│  Task & Output │  Knowledge (RAG)   │  Document Loaders      │
│  Team          │  Workflow Engine    │  Text Splitters        │
│  Policy System │  Guardrails        │  Anonymizer            │
│  LLM (OpenAI · Anthropic · Gemini · Groq · Ollama)          │
│  Observability (Audit · Metrics · Cost · Tracing)            │
│  Security (RBAC · Circuit Breaker · Rate Limiting)           │
│  FinTech (KYC · AML · Risk · Settlement · FX · Compliance)  │
└──────────────────────────────────────────────────────────────┘
```

---

## Özellikler

### Core
- **Agent** — tool-driven, yapılandırılmış görevler için (role/goal/instructions kimliği)
- **AutonomousAgent** — workspace içinde plan-yürüt-yansıt döngüsü
- **Task** — per-task tool override, structured output, multimodal input, system prompt
- **Structured Output** — Pydantic `response_format` ile tipli çıktı (JSON code fence parse)
- **Thinking / Reflection** — extended thinking (Anthropic/Gemini) + self-critique loop
- **Team** — `SEQUENTIAL`, `COORDINATE`, `ROUTE` modları

### RAG & Knowledge
- **KnowledgeBase** — TF-IDF veya ChromaDB backend ile semantic arama
- **Document Loaders** — txt, md, csv, json, pdf, docx, html (7 loader)
- **Text Splitters** — Recursive, Markdown, Sentence, Fixed (4 splitter)
- **Embedding** — Hash, OpenAI, Gemini, SentenceTransformer

### Safety & Security
- **Guardrails** — PII detection, prompt injection detection
- **Anonymizer** — tersinir PII maskeleme (anonymize → LLM → de-anonymize)
- **Policy System** — BLOCK / ANONYMIZE / REPLACE / LOG / RAISE aksiyonları
- **Built-in Policies** — PII, financial data, prompt injection
- **RBAC** — role-based access control
- **Sandbox** — workspace-restricted dosya I/O + allowlist'li shell

### Enterprise
- **Workflow Engine** — DAG tabanlı, koşullu dallanma, paralel, onay düğümleri
- **Session Management** — InMemory, Redis, SQLite backend'leri (TTL destekli)
- **Circuit Breaker** — otomatik devre kesici (resilience pattern)
- **Rate Limiting** — token bucket + scope-based API koruması
- **Idempotency** — tool idempotency store
- **Audit Log** — tamper-proof hash chain denetim izi
- **Cost Tracker** — model bazlı token/USD takibi
- **Metrics** — counter, gauge, histogram, timer

### LLM Provider'lar
- **Anthropic** — Claude (streaming + tool calling + extended thinking)
- **OpenAI** — GPT-4o, o1, o3 (streaming + tool calling)
- **Google Gemini** — Gemini 2.5 Flash/Pro (streaming + tool calling + thinking)
- **Groq** — LLaMA, Mixtral (streaming + tool calling)
- **Ollama** — Yerel modeller (streaming + tool calling)

### FinTech
- TC kimlik, IBAN, VKN doğrulama
- Sanctions/PEP/structuring/velocity AML
- Transaction & merchant risk scoring
- Reconcile + komisyon hesabı
- FX; KVKK saklama; BSMV
- Hazır agent'lar: `OnboardingAgent`, `AMLAgent`, `SettlementAgent`, `PeriodicControlAgent`

---

## Kurulum

```bash
cd auraOS
pip install -e .

# opsiyonel ekstralar
pip install -e ".[anthropic]"   # Anthropic SDK
pip install -e ".[openai]"      # OpenAI SDK
pip install -e ".[google]"      # Google Gemini SDK
pip install -e ".[groq]"        # Groq SDK
pip install -e ".[ollama]"      # Ollama SDK
pip install -e ".[rag]"         # Chroma + sentence-transformers
pip install -e ".[loaders]"     # PDF + DOCX + HTML loaders
pip install -e ".[fintech]"     # yfinance + pandas
pip install -e ".[all]"         # hepsi
```

---

## Hızlı Başlangıç

### Basit Agent

```python
from auraos import Agent, Task, tool

@tool
def hesapla(a: int, b: int) -> int:
    """İki sayıyı toplar."""
    return a + b

agent = Agent(
    name="Hesapçı",
    model="anthropic/claude-sonnet-4-5",
    tools=[hesapla],
)

response = agent.run(Task("5 ile 7'yi topla"))
print(response.output)         # "12"
print(response.tool_calls)     # [ToolCall(name='hesapla', result=12, ...)]
```

### Agent Kimliği (Role / Goal / Instructions)

```python
agent = Agent(
    name="Kredi Analisti",
    model="gemini/gemini-2.5-flash",
    role="Kıdemli kredi risk analisti",
    goal="Kredi başvurularını doğru değerlendir",
    instructions="Türkçe yanıt ver, risk skorunu 0-100 arasında belirt",
    tools=[kkb_sorgula, masak_kontrol],
)
```

### Structured Output (Pydantic)

```python
from pydantic import BaseModel

class KrediKarari(BaseModel):
    onay: bool
    risk_skoru: float
    gerekce: str

task = Task(
    description="Mehmet Bey'in kredi başvurusunu değerlendir",
    response_format=KrediKarari,
)

result = agent.run(task)
print(result.parsed)  # KrediKarari(onay=True, risk_skoru=0.25, gerekce="...")
```

### Thinking + Reflection

```python
agent = Agent(
    name="Stratejist",
    model="anthropic/claude-sonnet-4-5",
    thinking_enabled=True,    # Extended thinking
    thinking_budget=10000,    # Token bütçesi
    reflection=True,          # Cevabı eleştir → iyileştir
)
```

### Per-Task Tool Override & Multimodal

```python
task = Task(
    description="Bu kimlik kartını doğrula",
    tools=[ocr_tool, tc_dogrula],     # Sadece bu task için tool'lar
    images=["kimlik_on.jpg"],          # Multimodal input
    system_prompt="Kimlik doğrulama uzmanısın",
)
```

---

## RAG & Knowledge Base

```python
from auraos import KnowledgeBase, RecursiveSplitter

kb = KnowledgeBase(
    splitter=RecursiveSplitter(chunk_size=500, overlap=50),
)

# Metin ekle
kb.add("Uzun döküman metni...")

# Dosyadan yükle (otomatik loader seçimi)
kb.add_file("rapor.pdf")
kb.add_file("veriler.csv")
kb.add_file("politikalar.md")

# Agent'a bağla
agent = Agent(
    name="Araştırmacı",
    model="gemini/gemini-2.5-flash",
    knowledge=kb,
)
```

**Desteklenen formatlar:** `.txt`, `.md`, `.csv`, `.json`, `.pdf`, `.docx`, `.html`

**Splitter'lar:** `RecursiveSplitter`, `MarkdownSplitter`, `SentenceSplitter`, `FixedSplitter`

---

## Safety & Policy

### Anonymize / De-anonymize

```python
from auraos import Agent, Guardrails

agent = Agent(
    name="Müşteri Temsilcisi",
    model="anthropic/claude-sonnet-4-5",
    guardrails=Guardrails(pii_anonymize=True),
)

# Input:  "TC: 12345678901, mail: user@test.com"
# LLM'e: "TC: <TC_KIMLIK_1>, mail: <EMAIL_1>"
# Output: Orijinal değerler otomatik geri konur
```

### Policy System

```python
from auraos.security.policy import (
    pii_policy, financial_data_policy, prompt_injection_policy,
    Policy, PolicyRule, PolicyAction,
)

# Hazır policy'ler
pii = pii_policy(action=PolicyAction.ANONYMIZE)
fin = financial_data_policy(action=PolicyAction.REPLACE)
inj = prompt_injection_policy()  # BLOCK

# Özel policy
import re
custom = Policy(name="gizli_veri", rules=[
    PolicyRule(name="gizli", pattern=re.compile(r"GİZLİ"), action=PolicyAction.BLOCK),
])

result = fin.apply("Bakiye: 1.500,00 TL")
# result.ok=False, result.hits=[{rule: "balance", ...}]
```

**Aksiyonlar:** `BLOCK`, `ANONYMIZE`, `REPLACE`, `LOG`, `RAISE`

**Finansal pattern'ler:** IBAN, kredi kartı, hesap bakiyesi (`1.500,00 TL`), maaş/gelir

---

## Session Management

```python
from auraos import SessionManager, SQLiteSessionStore

# SQLite — process restart'larında bile korunur
store = SQLiteSessionStore(db_path="sessions.db", ttl_seconds=86400)
sm = SessionManager(store=store)

agent = Agent(
    name="Asistan",
    model="gemini/gemini-2.5-flash",
    session_manager=sm,
)

# Aynı session_id ile çağır → sohbet geçmişi korunur
result = agent.run("Merhaba", session_id="user_123")
result = agent.run("Az önce ne dedim?", session_id="user_123")
```

**Backend'ler:** `InMemorySessionStore`, `RedisSessionStore`, `SQLiteSessionStore`

---

## Workflow Engine

```python
from auraos.workflow import workflow, node, condition, approval, WorkflowExecutor

@node(transitions=["risk_kontrol"])
def kyc_dogrula(state):
    return {"kyc_result": "PASS"}

@condition(branches={"approve": "onayla", "reject": "reddet"})
def risk_kontrol(state):
    return "approve" if state["kyc_result"] == "PASS" else "reject"

@approval(transitions=["onayla"])
def yonetici_onay(state):
    return {"approval": True}

@node()
def onayla(state):
    return {"status": "APPROVED"}

wf = workflow("kredi_akisi", start="kyc_dogrula")
executor = WorkflowExecutor(wf)
result = executor.run()
```

---

## Multi-Agent Team

```python
from auraos import Agent, Team, TeamMode, Task

researcher = Agent(name="Araştırmacı", model="gemini/gemini-2.5-flash")
writer = Agent(name="Yazar", model="anthropic/claude-sonnet-4-5")

team = Team(
    agents=[researcher, writer],
    mode=TeamMode.SEQUENTIAL,
)
result = team.run(Task("Türkiye fintech trendleri raporu hazırla"))
```

**Modlar:** `SEQUENTIAL` (sıralı), `COORDINATE` (lider planlama), `ROUTE` (task'a göre yönlendirme)

---

## FinTech

```python
from auraos.fintech.kyc import kyc_summary
from auraos.fintech.aml import aml_assessment

kyc = kyc_summary(
    full_name="Mehmet Demo",
    tc_no="12345678901",
    birth_date="1990-05-15",
    address="Atatürk Cd. No:1 Kadıköy/İstanbul",
)

aml = aml_assessment(
    name="Mehmet Demo",
    transactions=[
        {"amount": 9500, "date": "2026-04-01"},
        {"amount": 9700, "date": "2026-04-02"},
    ],
    country="TR",
)
```

---

## Mimari

### Agent Yürütme Döngüsü

```
Task → Agent.run()
   ├─ Guardrails: input kontrol + PII anonymize
   ├─ system_prompt (role/goal/instructions) + RAG context + session/memory
   ├─ Per-task tool override (varsa geçici registry)
   ├─ LLM.complete(messages, tools, thinking?)
   │    ├─ tool_calls varsa → registry.invoke() → result LLM'e geri
   │    └─ yoksa → final_output
   ├─ Reflection (varsa): critique → improve → final
   ├─ Structured output parse (varsa): JSON → Pydantic model
   ├─ PII de-anonymize
   ├─ Guardrails: output kontrol
   └─ AgentResponse(output, parsed, tool_calls, iterations, tokens, duration)
```

### Bileşenler

| Modül | Sorumluluk |
|-------|------------|
| `core` | `Agent`, `AutonomousAgent`, `Task`, `AgentResponse` |
| `tools` | `@tool`, `ToolRegistry`, sub-agent tool, agent router |
| `llm` | Provider abstraction (Anthropic/OpenAI/Gemini/Groq/Ollama) |
| `memory` | Session management (InMemory/Redis/SQLite) |
| `knowledge` | RAG (TF-IDF/Chroma), loaders (7 format), splitters (4 tip) |
| `team` | Sequential / Coordinate / Route koordinasyonu |
| `workflow` | DAG tabanlı WorkflowExecutor |
| `guardrails` | PII detect/redact, prompt injection, Anonymizer |
| `security` | RBAC, Policy System (PII/financial/injection policies) |
| `observability` | AuditLog, CostTracker, Metrics, Tracer |
| `sandbox` | `Workspace` + `SafeShell` |
| `fintech` | KYC/AML/Risk/Settlement/FX/Compliance + hazır agent'lar |
| `utils` | Cache, RateLimiter, CircuitBreaker, Idempotency |

---

## Klasör Yapısı

```
auraOS/
├── auraos/
│   ├── core/            # Agent, AutonomousAgent, Task, Response
│   ├── tools/           # @tool, registry, schema, context, subagent
│   ├── llm/             # base + providers/{anthropic,openai,gemini,groq,ollama}
│   ├── memory/          # session (InMemory, Redis, SQLite)
│   ├── knowledge/       # base (RAG), document, chunker, loaders, splitters
│   ├── team/            # Team + modlar
│   ├── workflow/        # DAG executor, state store
│   ├── security/        # RBAC, Policy system
│   ├── sandbox/         # Workspace, SafeShell
│   ├── fintech/         # kyc, aml, risk, settlement, market, fx, compliance
│   ├── observability/   # audit, cost, metrics, tracer, structured_logger
│   ├── utils/           # cache, rate_limit, circuit_breaker, idempotency, logger
│   ├── guardrails.py    # PII, prompt injection, Anonymizer
│   ├── config.py        # YAML/env konfigürasyon
│   └── cli.py           # `auraos` CLI
├── examples/
├── tests/               # 159 test (50 v0.4)
├── docs/
├── pyproject.toml
└── README.md
```

---

## Test

```bash
# Tüm testler
pytest tests/ -v --ignore=tests/test_chatbot.py --ignore=tests/test_llm_integration.py

# Sadece v0.4 testleri
pytest tests/test_v04.py -v

# 159 passed, 42 skipped (API key olmadan)
```

---

## Upsonic ile Karşılaştırma

| Özellik | auraOS v0.4 | Upsonic |
|---------|-------------|---------|
| Agent (tool-driven + otonom) | ✅ | ✅ |
| Agent kimliği (role/goal/instructions) | ✅ | ✅ |
| Task abstraction + structured output | ✅ | ✅ |
| Thinking / Reflection | ✅ | ✅ |
| Anonymize / De-anonymize | ✅ | ✅ |
| Policy System (PII/financial/custom) | ✅ | ✅ |
| LLM provider'lar | ✅ (6) | ✅ (30+) |
| Multi-agent Team | ✅ | ✅ |
| RAG + Loaders + Splitters | ✅ | ✅ |
| Persistent session (SQLite) | ✅ | ✅ |
| Workflow Engine (DAG) | ✅ | ❌ |
| RBAC + Audit + Circuit Breaker | ✅ | ❌ |
| FinTech (TR regülasyon) | ✅ | ❌ |
| MCP desteği | 🔜 | ✅ |
| FastAPI / Deployment | 🔜 | ✅ |
| Skills sistemi | 🔜 | ✅ |
| Lisans | MIT | MIT |

**auraOS'un farkı:** Workflow engine, RBAC, tamper-proof audit, circuit breaker, Türkiye finans regülasyonuna özel tool'lar (TC kimlik, MASAK, KVKK, BSMV).

---

## Yol Haritası

- [ ] MCP Client — external MCP server bağlantısı
- [ ] FastAPI entegrasyonu — REST API sunucu
- [ ] Durable Execution — agent state checkpoint + resume
- [ ] User Input HITL — agent'ın kullanıcıdan bilgi istemesi
- [ ] OpenTelemetry — span-based tracing export
- [ ] Summary Memory — LLM ile otomatik özet
- [ ] Skills System — paketlenmiş domain bilgisi
- [ ] OCR Pipeline — multi-engine orchestration

---

## Lisans

MIT
