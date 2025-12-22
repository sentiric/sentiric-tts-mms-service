# 🚀 Sentiric MMS-TTS Service v1.2 (Production Ready)

[![Status](https://img.shields.io/badge/status-production_ready-success.svg)]()
[![Engine](https://img.shields.io/badge/engine-Facebook_MMS-blue.svg)]()
[![TTFB](https://img.shields.io/badge/TTFB-%3C600ms-brightgreen.svg)]()
[![gRPC](https://img.shields.io/badge/gRPC-supported-blue.svg)]()
[![AI Contract](https://img.shields.io/badge/Contract-v1.12.3-success.svg)]()

**Sentiric MMS-TTS Service**, Facebook'un Massively Multilingual Speech (MMS) modelini temel alan, yüksek performanslı ve düşük gecikmeli bir Türkçe metin-ses dönüştürme (TTS) mikroservisidir. Coqui XTTS servisiyle **tam eşdeğer yetenek seti** sunmayı hedefler.

## 🚀 Temel Yetenekler

*   **CPU/GPU Optimize:** CUDA destekli GPU veya CPU üzerinde çalışır.
*   **Caching:** Aynı metin ve parametreler için tekrar sentezleme maliyetini ortadan kaldırır.
*   **Streaming API:** Düşük gecikmeli ses akışı sunar (Pseudo-Streaming).
*   **gRPC & REST API:** Hem iç servisler hem de dış dünya için esnek erişim.
*   **OpenAI Uyumlu API:** Mevcut istemcilerle kolay entegrasyon.
*   **Prometheus Metrikleri:** Ölçeklenebilirlik ve izleme için standart metrikler.
*   **Gelişmiş Konfigürasyon:** Ortam değişkenleri ile kolay yapılandırma (`pydantic-settings`).
*   **Cache & History:** Konuşma geçmişi ve tekrar istekler için disk tabanlı depolama.

## 🛠️ Kurulum ve Çalıştırma

### Ön Gereksinimler
- Docker & Docker Compose
- NVIDIA Container Toolkit (GPU kullanımı için)

### Adımlar

1.  **Projeyi Klonla:**
    ```bash
    git clone https://github.com/sentiric/sentiric-tts-mms-service.git
    cd sentiric-tts-mms-service
    ```

2.  **Docker Compose ile Başlat:**
    ```bash
    # CPU için: TTS_MMS_SERVICE_DEVICE=cpu docker compose up -d
    docker compose up -d --build
    ```
    *Bu komut, tüm bağımlılıkları ve MMS modelini imajın içine gömerek build işlemini yapar.*

---

## ⚡ API Kullanımı ve Testler

### 1. Health Check
```bash
curl http://localhost:14060/health
# Beklenen Çıktı: {"status":"ok", "model_loaded":true, "device":"cuda", "model_id":"facebook/mms-tts-tur", "sample_rate":16000}
```

### 2. Internal TTS API (REST)
```bash
# Unary İstek
curl -X POST http://localhost:14060/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu, Sentirik platformu için oluşturulmuş standart bir ses testidir. Sistem normal çalışıyor.", "output_format": "wav"}' \
  --output test_unary.wav

# Streaming İstek (Pseudo-Streaming)
curl -X POST http://localhost:14060/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Bu, Sentirik platformu için oluşturulmuş canlı bir ses testidir. Sistem normal çalışıyor.", "stream": true}' \
  --output test_stream.pcm
```

### 3. OpenAI Uyumlu API (REST)
```bash
curl -X POST http://localhost:14060/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Bu, Sentirik platformu için oluşturulmuş open ui uyumlu bir ses testidir. Sistem normal çalışıyor.", "voice": "alloy"}' \
  --output openai_test.wav
```

### 4. gRPC API Testi

*   `sentiric-contracts` deposundan protobuf'ları derleyin: `make generate-all`
*    Ardından `tests/grpc_client.py` betiğini çalıştırın: `python3 tests/grpc_client.py`

---

## Üretim Hazırlığı ve Sürdürülebilirlik

*   **Persistent Volumes:** Kalıcı depolama için `/app/cache` ve `/app/history` dizinleri Docker volume'ları ile mount edilmelidir.
*   **CI/CD Pipeline:** GitHub Actions, otomatik build, test ve `ghcr.io/sentiric/tts-mms-service:latest` imajının yayınlanmasını sağlamalıdır.
*   **Monitoring:** `/metrics` endpoint'i Prometheus tarafından çekilmeli ve Grafana ile görselleştirilmelidir.

---

**(c) 2025 Sentiric Platform Team**