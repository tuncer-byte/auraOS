# auraOS

> **Finansal AI Agent Framework** — Upsonic'ten esinlenerek geliştirilmiş, finans odaklı, açık kaynak Python framework'ü.

`auraOS`; otonom (autonomous) ve geleneksel (tool-driven) agent mimarilerini, multi-agent koordinasyonunu, RAG bilgi tabanını, sandbox'lı yürütme katmanını ve hazır FinTech tool/agent'larını tek bir pakette sunar.

```
┌─────────────────────────────────────────────────────────┐
│                       auraOS                            │
├─────────────────────────────────────────────────────────┤
│  Core      │  Tools    │  Memory   │  Knowledge (RAG)   │
│  Agents    │  Sandbox  │  Team     │  Observability     │
│  LLM (OpenAI/Anthropic/Google/Ollama/Mock)              │
│  FinTech (KYC · AML · Risk · Settlement · FX · ...)     │
└─────────────────────────────────────────────────────────┘
```

---

## Özellikler

- **Agent**: tool-driven, yapılandırılmış görevler için.
- **AutonomousAgent**: workspace içinde plan-yürüt-yansıt döngüsü.
- **Tool sistemi**: `@tool` dekoratörü → otomatik JSON schema (OpenAI/Anthropic uyumlu).
- **LLM provider'lar**: OpenAI, Anthropic, Google, Ollama, Mock.
- **Memory**: Conversation (in-memory/SQLite), Focus, Summary.
- **Knowledge Base**: TF-IDF veya Chroma backend ile RAG.
- **Team**: `SEQUENTIAL`, `COORDINATE`, `ROUTE` modları.
- **Sandbox**: workspace-restricted dosya I/O + allowlist'li shell.
- **FinTech**: TC kimlik, IBAN, VKN doğrulama; sanctions/PEP/structuring/velocity AML; transaction & merchant risk; reconcile + komisyon hesabı; FX; KVKK saklama.
- **Hazır agent'lar**: `OnboardingAgent`, `AMLAgent`, `SettlementAgent`, `PeriodicControlAgent`.
- **Observability**: JSONL tracer (Langfuse/PromptLayer'a yönlendirilebilir).

---

## Kurulum

```bash
cd auraOS
pip install -e .

# opsiyonel ekstralar
pip install -e ".[anthropic]"   # Anthropic SDK
pip install -e ".[openai]"      # OpenAI SDK
pip install -e ".[rag]"         # Chroma + sentence-transformers
pip install -e ".[fintech]"     # yfinance + pandas
pip install -e ".[all]"         # hepsi
```

---

## Hızlı Başlangıç

```python
from auraos import Agent, Task, tool

@tool
def hesapla(a: int, b: int) -> int:
    """İki sayıyı toplar.

    Args:
        a: İlk sayı
        b: İkinci sayı
    """
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

### LLM olmadan denemek

```python
from auraos.llm.providers.mock import MockLLM
llm = MockLLM(scripted=[
    {"tool_calls": [{"id": "1", "name": "hesapla", "arguments": {"a": 5, "b": 7}}]},
    {"content": "Sonuç 12."},
])
agent = Agent(tools=[hesapla], llm=llm)
```

---

## FinTech Kullanımı

### KYC + AML

```python
from auraos.fintech.kyc import kyc_summary
from auraos.fintech.aml import aml_assessment

kyc = kyc_summary(
    full_name="Mehmet Demo",
    tc_no="12345678901",
    birth_date="1990-05-15",
    address="Atatürk Cd. No:1 Kadıköy/İstanbul",
)
# {'decision': 'REJECT'/'PASS', 'flags': [...]}

aml = aml_assessment(
    name="Mehmet Demo",
    transactions=[
        {"amount": 9500, "date": "2026-04-01"},
        {"amount": 9700, "date": "2026-04-02"},
        {"amount": 9800, "date": "2026-04-03"},
    ],
    country="TR",
)
# {'decision': 'BLOCK'/'EDD'/'MONITOR'/'PASS', 'score': 30, 'components': {...}}
```

### Hazır Agent'lar

```python
from auraos.fintech import OnboardingAgent, AMLAgent
from auraos import Team, TeamMode, Task

team = Team(
    agents=[OnboardingAgent(), AMLAgent()],
    mode=TeamMode.SEQUENTIAL,
)
team.run(Task("Mehmet Demo (TC: 12345678901) müşterisini onboard et ve AML değerlendir"))
```

---

## Mimari

### Bileşenler

| Modül | Sorumluluk |
|-------|------------|
| `core` | `Agent`, `AutonomousAgent`, `Task`, `AgentResponse` |
| `tools` | `@tool`, `ToolRegistry`, `schema`, sandbox builtins |
| `llm` | Provider abstraction (OpenAI/Anthropic/Google/Ollama/Mock) |
| `memory` | Conversation / Focus / Summary belleği |
| `knowledge` | TF-IDF veya Chroma tabanlı RAG |
| `team` | Sequential / Coordinate / Route koordinasyonu |
| `sandbox` | `Workspace` + `SafeShell` (path traversal & komut allowlist) |
| `observability` | JSONL trace üretimi |
| `fintech` | KYC/AML/Risk/Settlement/FX/Compliance + hazır agent'lar |

### Agent Yürütme Döngüsü

```
Task → Agent.run()
   ├─ system_prompt + RAG context + memory geçmişi
   ├─ LLM.complete(messages, tools)
   │    ├─ tool_calls varsa → registry.invoke() → result LLM'e geri
   │    └─ yoksa → final_output
   └─ AgentResponse(output, tool_calls, iterations, tokens, duration)
```

### Güvenlik

- Tüm `read_file`/`write_file`/`run_shell` çağrıları `Workspace` dışına çıkamaz.
- Mutlak yol ve `..` traversal — `WorkspaceSecurityError`.
- Shell, allowlist + tehlikeli desen reddi (rm -rf /, mkfs, sudo, …).
- Kritik tool'lar için `requires_approval=True` ile insan-onayı işareti.

---

## Klasör Yapısı

```
auraOS/
├── auraos/
│   ├── core/            # Agent, AutonomousAgent, Task, Response
│   ├── tools/           # @tool, registry, schema, builtins
│   ├── llm/             # base + providers/{openai,anthropic,google,ollama,mock}
│   ├── memory/          # base, conversation, focus, summary
│   ├── knowledge/       # base (RAG), document, chunker
│   ├── team/            # Team + modlar
│   ├── sandbox/         # Workspace, SafeShell
│   ├── fintech/         # kyc, aml, risk, settlement, market, fx, compliance + agents
│   ├── observability/   # tracer (JSONL)
│   ├── utils/           # logger
│   └── cli.py           # `auraos` CLI
├── examples/            # 5 hazır örnek
├── tests/               # 18 birim test
├── docs/                # ARCHITECTURE.md, ROADMAP.md
├── pyproject.toml
└── README.md
```

---

## CLI

```bash
auraos info                                  # bileşenleri listele
auraos run "5 ile 7'yi topla" --model mock/demo
auraos onboard --name "Ali" --tc 12345678901 --birth 1990-01-01 --address "İstanbul"
auraos run "rapor.md oluştur" --autonomous --workspace ./ws
```

---

## Test

```bash
pytest tests/ -q
# 18 passed
```

---

## Upsonic ile Karşılaştırma

| Özellik | auraOS | Upsonic |
|---------|--------|---------|
| Otonom + Traditional Agent | ✅ | ✅ |
| Sandbox (workspace) | ✅ | ✅ |
| LLM provider abstraction | ✅ (5+) | ✅ (30+) |
| Multi-agent (Sequential/Coordinate/Route) | ✅ | ✅ |
| RAG (TF-IDF + Chroma) | ✅ | ✅ |
| MCP desteği | 🔜 (yol haritasında) | ✅ |
| FinTech tool'ları (TR odaklı) | ✅ (TC/IBAN/VKN/MASAK) | ⚠️ genel |
| Hazır FinTech agent'ları | ✅ | ✅ |
| Lisans | MIT | MIT |
| Boyut | minimal | geniş |

**auraOS'un farkı:** Türkiye finans regülasyonuna özel (TC kimlik checksum, MASAK eşik mantığı, KVKK saklama, BSMV) tool'ları kutudan çıkar çıkmaz sunması ve ince/anlaşılır bir kod tabanı olması.

---

## Yol Haritası

- [ ] MCP (Model Context Protocol) istemcisi
- [ ] Postgres/Redis memory backend'leri
- [ ] OCR pipeline (TR kimlik kartı, fatura)
- [ ] FastAPI tabanlı HTTP server modu
- [ ] MASAK / OFAC API gerçek bağlayıcılar
- [ ] Langfuse entegrasyonu
- [ ] Kubernetes/Helm chart

---

## Lisans

MIT
