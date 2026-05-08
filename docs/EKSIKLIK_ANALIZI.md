# auraOS Eksiklik Analizi ve Geliştirme Planı

## Mevcut Durum

| Metrik | Değer |
|--------|-------|
| Toplam Kod | ~3000 satır |
| Modül Sayısı | 12 |
| Test Sayısı | 18 |
| LLM Provider | 5 (OpenAI, Anthropic, Gemini, Ollama, Mock) |

---

## 1. KRİTİK EKSİKLER (Öncelik: YÜKSEK)

### 1.1 Streaming Desteği Yok
**Sorun:** LLM cevapları tek seferde geliyor, kullanıcı bekliyor.
**Etki:** Kötü UX, uzun cevaplarda timeout riski.

```python
# MEVCUT (kötü)
response = llm.complete(messages)  # 10 saniye bekle, sonra tüm cevap

# OLMASI GEREKEN
async for chunk in llm.stream(messages):
    yield chunk  # Anlık görüntüleme
```

**Çözüm:**
- `BaseLLM.stream()` metodu ekle
- Her provider için streaming implementasyonu
- FastAPI'de SSE (Server-Sent Events) endpoint

---

### 1.2 Async/Await Desteği Eksik
**Sorun:** Tüm kod senkron, I/O blocking.
**Etki:** Yüksek yük altında performans düşüşü.

```python
# MEVCUT
def complete(self, messages): ...  # Blocking

# OLMASI GEREKEN
async def complete(self, messages): ...  # Non-blocking
async def acomplete(self, messages): ...  # Alternatif
```

**Çözüm:**
- `httpx.AsyncClient` kullan
- `aiofiles` ile async dosya I/O
- Agent.run() → Agent.arun()

---

### 1.3 Conversation Memory Session Yönetimi Yok
**Sorun:** Her istek bağımsız, önceki konuşma hatırlanmıyor.
**Etki:** Chatbot'ta "az önce ne sordum" çalışmıyor.

```python
# MEVCUT
agent.run("Merhaba")  # Session yok
agent.run("Az önce ne dedim?")  # Bilmiyor!

# OLMASI GEREKEN
agent.run("Merhaba", session_id="user_123")
agent.run("Az önce ne dedim?", session_id="user_123")  # Hatırlıyor
```

**Çözüm:**
- SessionManager sınıfı
- Redis/PostgreSQL session storage
- TTL (Time-To-Live) ile otomatik temizleme

---

### 1.4 Error Handling Zayıf
**Sorun:** Hatalar düzgün yakalanmıyor, kullanıcıya ham hata gidiyor.
**Etki:** Güvenlik riski, kötü UX.

```python
# MEVCUT
try:
    result = tool()
except Exception as e:
    result = {"error": str(e)}  # Ham hata!

# OLMASI GEREKEN
try:
    result = tool()
except ValidationError as e:
    raise ToolValidationError(tool_name, e)
except TimeoutError:
    raise ToolTimeoutError(tool_name, timeout)
except Exception as e:
    logger.error(f"Tool {tool_name} failed", exc_info=True)
    raise ToolExecutionError(tool_name, "Beklenmeyen hata")
```

**Çözüm:**
- Custom exception hierarchy
- Retry mekanizması (tenacity)
- Graceful degradation

---

### 1.5 Rate Limiting Yok
**Sorun:** API'ler sınırsız çağrılabilir.
**Etki:** Maliyet patlaması, API ban riski.

**Çözüm:**
- Token bucket / sliding window limiter
- Provider başına limit konfigürasyonu
- Usage tracking ve alerting

---

## 2. ÖNEMLİ EKSİKLER (Öncelik: ORTA)

### 2.1 Tool Validation Eksik
**Sorun:** Tool parametreleri runtime'da validate edilmiyor.
**Etki:** LLM yanlış parametre gönderirse crash.

```python
# MEVCUT
def murabaha_calculate(cost_price: float, ...):
    # cost_price negatif olabilir!

# OLMASI GEREKEN
@tool
@validate_params
def murabaha_calculate(
    cost_price: Annotated[float, Gt(0)],  # > 0 olmalı
    profit_rate: Annotated[float, Ge(0), Le(1)],  # 0-1 arası
    ...
):
```

**Çözüm:**
- Pydantic model integration
- JSON Schema validation
- Custom validators

---

### 2.2 Caching Yok
**Sorun:** Aynı sorgu tekrar tekrar LLM'e gidiyor.
**Etki:** Gereksiz maliyet ve latency.

**Çözüm:**
```python
@lru_cache(maxsize=1000)
def cached_embedding(text: str) -> list[float]: ...

# Veya Redis cache
cache = RedisCache(ttl=3600)
response = cache.get_or_compute(key, lambda: llm.complete(msg))
```

---

### 2.3 Embedding Sağlayıcı Yok
**Sorun:** KnowledgeBase TF-IDF kullanıyor, semantic search zayıf.
**Etki:** RAG kalitesi düşük.

**Çözüm:**
- OpenAI embeddings
- Sentence Transformers (local)
- Cohere/Voyage embeddings

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class OpenAIEmbedding(EmbeddingProvider): ...
class SentenceTransformerEmbedding(EmbeddingProvider): ...
```

---

### 2.4 Observability Zayıf
**Sorun:** Sadece JSONL log var, gerçek zamanlı monitoring yok.
**Etki:** Production'da debug zorluğu.

**Çözüm:**
- OpenTelemetry integration
- Langfuse/LangSmith entegrasyonu
- Prometheus metrics
- Structured logging (JSON)

---

### 2.5 Human-in-the-Loop Eksik
**Sorun:** `requires_approval` flag var ama çalışmıyor.
**Etki:** Kritik işlemlerde onay alınamıyor.

**Çözüm:**
```python
@tool(requires_approval=True)
def transfer_money(amount: float, to_account: str):
    # Bu tool çağrıldığında:
    # 1. Agent durur
    # 2. Kullanıcıya onay sorusu gider
    # 3. Onay gelirse devam eder
    ...
```

---

## 3. GELİŞTİRME ÖNERİLERİ (Öncelik: DÜŞÜK)

### 3.1 MCP (Model Context Protocol) Desteği
- Binlerce harici tool'a erişim
- Standardize tool interface

### 3.2 Multi-Modal Destek
- Görsel anlama (belge OCR)
- Ses girişi (telefon bankacılığı)

### 3.3 Fine-tuning Pipeline
- Domain-specific model training
- LoRA/QLoRA support

### 3.4 A/B Testing Framework
- Prompt varyasyonları test
- Model karşılaştırma

### 3.5 Guardrails
- PII detection/redaction
- Prompt injection koruması
- Output validation

---

## 4. KOD KALİTESİ SORUNLARI

### 4.1 Type Hints Eksik
```python
# MEVCUT
def run(self, task):

# OLMASI GEREKEN
def run(self, task: Task | str) -> AgentResponse:
```

### 4.2 Docstring Eksik
Birçok fonksiyonda docstring yok veya yetersiz.

### 4.3 Test Coverage Düşük
- Mevcut: ~18 test
- Hedef: >100 test
- Coverage: %80+

### 4.4 Configuration Management
```python
# MEVCUT - hardcoded
max_iterations = 10

# OLMASI GEREKEN - config file
config = AuraOSConfig.from_yaml("config.yaml")
agent = Agent(config=config)
```

---

## 5. PERFORMANS SORUNLARI

### 5.1 Memory Leak Riski
- Conversation history sınırsız büyüyor
- Çözüm: Max context window + summarization

### 5.2 Cold Start Yavaşlığı
- Her istek için agent yeniden oluşturuluyor
- Çözüm: Connection pooling, lazy loading

### 5.3 Büyük Dosya Handling
- Workspace büyük dosyalarda yavaş
- Çözüm: Streaming read/write, chunking

---

## 6. GÜVENLİK SORUNLARI

### 6.1 API Key Exposure
```python
# RİSKLİ
print(f"Key: {api_key}")

# GÜVENLİ
print(f"Key: {api_key[:8]}...")
```

### 6.2 SQL Injection (Memory)
```python
# RİSKLİ
cursor.execute(f"SELECT * WHERE name = '{user_input}'")

# GÜVENLİ
cursor.execute("SELECT * WHERE name = ?", (user_input,))
```

### 6.3 Path Traversal (Sandbox)
- Mevcut koruma iyi ama sembolik link kontrolü eksik

---

## 7. ÖNCELİKLENDİRİLMİŞ EYLEM PLANI

### Sprint 1 (1 Hafta) - Kritik
- [ ] Async/await desteği
- [ ] Streaming response
- [ ] Session management
- [ ] Error handling iyileştirme

### Sprint 2 (1 Hafta) - Önemli
- [ ] Embedding provider
- [ ] Redis cache
- [ ] Tool validation (Pydantic)
- [ ] Rate limiting

### Sprint 3 (1 Hafta) - Kalite
- [ ] Langfuse entegrasyonu
- [ ] Test coverage %80
- [ ] Type hints tamamlama
- [ ] Config management

### Sprint 4 (1 Hafta) - Gelişmiş
- [ ] Human-in-the-loop
- [ ] MCP client
- [ ] Guardrails
- [ ] Multi-modal (OCR)

---

## 8. SONUÇ

| Kategori | Mevcut | Hedef |
|----------|--------|-------|
| Kod Kalitesi | 6/10 | 9/10 |
| Performans | 5/10 | 8/10 |
| Güvenlik | 7/10 | 9/10 |
| Özellikler | 6/10 | 9/10 |
| Test Coverage | 30% | 80% |
| Production Ready | ❌ | ✅ |

**Tahmini Süre:** 4 hafta (1 geliştirici, full-time)

**Öncelik Sırası:**
1. Streaming + Async (UX kritik)
2. Session Management (chatbot için şart)
3. Error Handling (güvenilirlik)
4. Embedding + Cache (maliyet optimizasyonu)
