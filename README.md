# 🚀 Sentiric MMS-TTS Service v1.1

[![Status](https://img.shields.io/badge/status-production_ready-success.svg)]()
[![Engine](https://img.shields.io/badge/engine-Facebook_MMS-blue.svg)]()
[![Latency](https://img.shields.io/badge/TTFB-%3C600ms-brightgreen.svg)]()

**Sentiric MMS-TTS Service**, Facebook'un Masif Çok Dilli (Massively Multilingual Speech) modelini temel alan, yüksek performanslı ve düşük gecikmeli bir Türkçe metin-ses dönüştürme (TTS) mikroservisidir.

Bu servis, XTTSv2'nin yavaşlık sorunlarını aşmak ve 1 saniyenin altında TTFB (Time-To-First-Byte) süresi sağlamak amacıyla tasarlanmıştır.

---

## 🏛️ Mimari ve Teknoloji

- **AI Motoru:** `facebook/mms-tts-tur` (Doğrudan Türkçe için eğitilmiş VITS modeli)
- **Altyapı:** Hugging Face `transformers` kütüphanesi
- **Servis Katmanı:** FastAPI (Asenkron)
- **Dağıtım:** Docker (İzole ve taşınabilir "Appliance" modeli)
- **Optimizasyon:** Tüm bağımlılıklar ve AI modeli, Docker imajının içine gömülerek (`bake-in`) her çalıştırmada tutarlı ve hızlı bir başlangıç (startup) süresi garanti edilir.

---

## 🛠️ Kurulum ve Çalıştırma

### Ön Gereksinimler
- Docker & Docker Compose
- NVIDIA GPU ve [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

### Adımlar

1.  **Projeyi Klonla:**
    ```bash
    git clone https://github.com/sentiric/sentiric-tts-mms-service.git
    cd sentiric-tts-mms-service
    ```

2.  **Docker Servisini Başlat:**
    Bu komut, Docker imajını oluşturacak, gerekli Python kütüphanelerini kuracak ve Facebook MMS modelini (~1.2 GB) imajın içine indirecektir. İlk build işlemi internet hızınıza bağlı olarak 5-15 dakika sürebilir.

    ```bash
    docker compose up --build
    ```

    Loglarda `✅ MMS Modeli başarıyla yüklendi.` ve `Uvicorn running on http://0.0.0.0:8000` mesajlarını gördüğünüzde servis kullanıma hazırdır.

---

## ⚡️ Kullanım ve Performans Testi

Servis, `/stream` adında tek bir endpoint sunar. Bu endpoint, verilen metni seslendirir ve `audio/wav` formatında stream eder.

### Hız Testi (TTFB)

Aşağıdaki `curl` komutu, servise bir istek gönderir, `mms_test.wav` adında bir ses dosyası oluşturur ve en önemlisi, **ilk ses parçasının ne kadar sürede geldiğini (TTFB)** ölçer.

**Test Komutu:**
```bash
curl -N -X POST "http://localhost:8000/stream" \
-H "Content-Type: application/json" \
-d '{
  "text": "Bu, Sentiric platformu için oluşturulmuş standart bir ses testidir. Sistem normal çalışıyor."
}' \
-o mms_test.wav -w "TTFB: %{time_starttransfer}s\n"
```

### Beklenen Sonuç

- **İlk İstek (Cold Start):** `TTFB: ~1.3s` civarında olmalıdır. Bu, modelin GPU'ya ilk kez yüklendiği süredir.
- **Sonraki İstekler (Warm):** `TTFB: ~0.6s` (600 milisaniye) veya altında olmalıdır. Bu, servisin gerçek performansını yansıtır.

Oluşturulan `mms_test.wav` dosyasını dinleyerek ses kalitesini ve telaffuz doğruluğunu kontrol edebilirsiniz.

---

**(c) 2025 Sentiric Platform Team**
