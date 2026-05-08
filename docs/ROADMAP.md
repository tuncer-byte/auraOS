# auraOS Yol Haritası

## v0.1 (mevcut)
- [x] Core Agent + AutonomousAgent
- [x] Tool sistemi (@tool + registry + schema üretimi)
- [x] LLM providers: OpenAI, Anthropic, Google, Ollama, Mock
- [x] Memory: Conversation (memory/SQLite), Focus, Summary
- [x] KnowledgeBase: TF-IDF + Chroma
- [x] Team: Sequential, Coordinate, Route
- [x] Sandbox: Workspace + SafeShell
- [x] FinTech: KYC, AML, Risk, Settlement, FX, Compliance, Market
- [x] Hazır agent'lar: Onboarding, AML, Settlement, PeriodicControl
- [x] CLI (`auraos run`, `auraos onboard`, `auraos info`)
- [x] 18 birim test
- [x] 5 örnek senaryo

## v0.2 — Entegrasyonlar
- [ ] MCP istemcisi (binlerce harici araca bağlanma)
- [ ] Postgres + Redis memory backend
- [ ] Pinecone + Qdrant + Weaviate vector store'ları
- [ ] OpenRouter + Groq + Bedrock provider'ları
- [ ] sentence-transformers tabanlı embedding wrapper

## v0.3 — Üretim Hazırlığı
- [ ] FastAPI HTTP server (REST + SSE streaming)
- [ ] Docker + docker-compose
- [ ] Kubernetes Helm chart
- [ ] Prometheus metrik exporter
- [ ] Langfuse + PromptLayer entegrasyonu

## v0.4 — TR FinTech Bağlayıcıları
- [ ] MASAK SAR/STR XML üretici
- [ ] OFAC SDN, BM, AB Sanctions list otomatik güncelleyici
- [ ] BKM POS verisi parser'ı
- [ ] e-Fatura/e-Arşiv okuyucu
- [ ] Merkez Bankası FX TCMB feed

## v0.5 — OCR + Belge AI
- [ ] TR kimlik kartı OCR (Tesseract + post-processing)
- [ ] Fatura/dekont OCR şablonları
- [ ] PDF imza doğrulama

## v0.6 — Güvenlik & Compliance
- [ ] Role-based access control (RBAC)
- [ ] Audit log otomatik imzalama (KVKK uyumu)
- [ ] PII redaksiyon middleware'i
- [ ] Prompt injection guardrails

## Uzun Vade
- [ ] Self-hosted UI (chat + agent management)
- [ ] Plugin marketplace
- [ ] Fine-tuning recipe'leri (TR finans corpus)
