# auraOS CLI Kullanım Kılavuzu

## Kurulum

```bash
# Temel kurulum (Gemini ile)
pip install auraos[google]

# Tüm provider'lar
pip install auraos[all]

# Geliştirme kurulumu (repo'dan)
cd auraOS
pip install -e ".[all]"
```

## API Key Tanımlama

CLI çalışması için en az bir LLM provider API anahtarı gerekli:

```bash
# Gemini (önerilen - ücretsiz tier var)
export GEMINI_API_KEY='your-key-here'

# OpenAI
export OPENAI_API_KEY='sk-...'

# Anthropic
export ANTHROPIC_API_KEY='sk-ant-...'

# Kalıcı yapma (.bashrc veya .zshrc)
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

## Komutlar

### `auraos version`

Kurulu framework sürümünü gösterir.

```bash
$ auraos version
auraOS v0.2.0
```

### `auraos info`

Framework bileşenlerini listeler.

```bash
$ auraos info
┌──────────────┬────────────────────────────────────────────────────┐
│ Kategori     │ Bileşenler                                         │
├──────────────┼────────────────────────────────────────────────────┤
│ Çekirdek     │ Agent, AutonomousAgent, Task, ...                  │
│ LLM          │ Gemini, OpenAI (GPT), Anthropic (Claude), Ollama  │
│ ...          │ ...                                                │
└──────────────┴────────────────────────────────────────────────────┘
```

### `auraos test`

Framework sağlık kontrolü (API key + modül import'u).

```bash
$ auraos test
auraOS Sağlık Kontrolü

✓ Versiyon: 0.2.0
✓ API key: GEMINI_API_KEY tanımlı
✓ Import: Tüm modüller yüklü

Framework hazır.
```

### `auraos run` — Hızlı Agent Çalıştır

Tek satırda agent oluştur ve prompt çalıştır.

```bash
# Basit soru
auraos run "Merhaba dünya"

# Math
auraos run "5 ile 7'yi topla ve sonucu açıkla"

# Model seçimi
auraos run "İstanbul hava durumu" --model anthropic/claude-sonnet-4-6
auraos run "JSON üret" -m openai/gpt-4o

# Iteration limiti
auraos run "Karmaşık analiz yap" --max-iter 20
```

**Parametreler:**
- `prompt` (zorunlu): Çalıştırılacak görev/soru
- `--model, -m`: LLM model (default: `gemini/gemini-2.5-flash`)
  - Format: `provider/model`
  - Örnekler: `gemini/gemini-2.5-pro`, `openai/gpt-4o-mini`, `anthropic/claude-haiku-4-5`
- `--max-iter`: Maksimum iteration (default: 10)
- `--autonomous, -a`: AutonomousAgent modu (dosya okuma/yazma yetkisi)
- `--workspace, -w`: Autonomous mod workspace yolu (default: `./workspace`)

### `auraos run --autonomous` — Dosya İşlemleri

AutonomousAgent, workspace içinde dosya okur/yazar/listeler.

```bash
# Workspace oluştur
mkdir my_workspace

# Rapor üret
auraos run "Bir rapor.md dosyası oluştur" --autonomous -w ./my_workspace

# Analiz yap
auraos run "workspace'teki tüm .py dosyalarını say" -a -w ./my_workspace

# Kod değiştir
auraos run "config.json içindeki 'debug' değerini true yap" -a
```

**Not:** Autonomous mod sandbox'lanmıştır; sadece `--workspace` içinde işlem yapar.

### `auraos onboard` — KYC/Onboarding Agent

Müşteri onboarding senaryosunu çalıştırır (Fintech KYC).

```bash
auraos onboard \
  --name "Mehmet Yılmaz" \
  --tc 12345678901 \
  --birth 1990-01-15 \
  --address "İstanbul/Kadıköy"

# Farklı model ile
auraos onboard \
  --name "Ayşe Demir" \
  --tc 98765432109 \
  --birth 1985-06-20 \
  --address "Ankara/Çankaya" \
  --model anthropic/claude-sonnet-4-6
```

**Çıktı örneği:**
```
KYC Sonucu: PASS
Müşteri bilgileri doğrulandı.
Risk skoru: 2/10 (düşük)
Onay: Hesap açılabilir.
```

## Kullanım Örnekleri

### Örnek 1: Matematik Sorusu

```bash
$ export GEMINI_API_KEY='...'
$ auraos run "Fibonacci serisinin ilk 10 elemanını yaz"

Görev: Fibonacci serisinin ilk 10 elemanını yaz

✓ Tamamlandı (1 iter, 1234ms)

Fibonacci serisinin ilk 10 elemanı:
0, 1, 1, 2, 3, 5, 8, 13, 21, 34
```

### Örnek 2: Dosya İşlemi (Autonomous)

```bash
$ auraos run "analiz.txt dosyası oluştur, içine bugünün tarihini yaz" -a -w ./demo

Agent başlatılıyor: gemini/gemini-2.5-flash
Görev: analiz.txt dosyası oluştur, içine bugünün tarihini yaz

✓ Tamamlandı (2 iter, 2567ms)

✓ Dosya oluşturuldu: analiz.txt
İçerik: 2026-05-08

Tool çağrıları: write_file
```

### Örnek 3: Model Karşılaştırma

```bash
# Gemini ile
time auraos run "Python'da quick sort implementasyonu yaz" -m gemini/gemini-2.5-flash

# Claude ile
time auraos run "Python'da quick sort implementasyonu yaz" -m anthropic/claude-sonnet-4-6

# GPT ile
time auraos run "Python'da quick sort implementasyonu yaz" -m openai/gpt-4o-mini
```

## Hata Çözümleri

### "No module named 'auraos'"

```bash
# Pip ile kurulu değil, tekrar kur
pip install auraos[google]

# Veya geliştirme kurulumu
cd auraOS && pip install -e ".[all]"
```

### "HATA: Hiçbir LLM provider API anahtarı bulunamadı"

```bash
# En az bir API key tanımla
export GEMINI_API_KEY='your-key-here'

# Veya
export OPENAI_API_KEY='sk-...'

# Test et
auraos test
```

### "Rate limit exceeded"

```bash
# Gemini free tier: 15 RPM
# Çözüm: API key'inizi upgrade edin veya bekleme süresi ekleyin

# Veya paralel istek atmayın; sıralı çağırın
auraos run "soru 1"
sleep 5
auraos run "soru 2"
```

### "Circuit breaker open"

LLM provider'ı 5 kez üst üste başarısız olmuş; 30 saniye sonra tekrar dener.

```bash
# 30 saniye bekle
sleep 30
auraos run "tekrar dene"
```

## İleri Seviye: Python Kodundan Kullanım

CLI sadece hızlı testler için; üretim kodunda doğrudan Python API kullanın:

```python
from auraos import Agent, Task

agent = Agent(model="gemini/gemini-2.5-flash")
result = agent.run(Task("Merhaba dünya"))
print(result.output)
```

Tüm enterprise özellikler (audit, cost, metrics, RBAC, circuit breaker, sessions) Python API'de mevcut; CLI'de henüz expose edilmemiş.

## Sık Kullanılan Komut Şablonları

```bash
# Hızlı soru-cevap
alias aura='auraos run'
aura "bugün hava nasıl"

# Varsayılan model değiştir
export AURAOS_DEFAULT_MODEL="anthropic/claude-sonnet-4-6"
auraos run "..." -m $AURAOS_DEFAULT_MODEL

# Log'ları göster (JSON format)
auraos run "test" 2>&1 | jq .

# Autonomous workspace reset
rm -rf ./workspace && mkdir workspace
auraos run "Yeni proje başlat" -a
```

## Özet Tablo

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `version` | Sürüm | `auraos version` |
| `info` | Bileşen listesi | `auraos info` |
| `test` | Sağlık kontrolü | `auraos test` |
| `run` | Hızlı agent | `auraos run "soru"` |
| `run -a` | Autonomous mod | `auraos run "dosya oku" -a` |
| `onboard` | KYC/Onboarding | `auraos onboard --name "..." --tc ...` |

**Tüm komutlar için detaylı yardım:**
```bash
auraos --help
auraos run --help
auraos onboard --help
```
