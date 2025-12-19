# Base Image: CUDA 11.8 ile uyumlu PyTorch 2.1.2
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

LABEL maintainer="Sentiric AI Team"
LABEL version="v1.1-mms-turkish-stable"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip libsndfile1 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# --- BAĞIMLILIKLAR (TÜM VERSİYONLAR KİLİTLENDİ) ---
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    "torch==2.1.2" "torchaudio==2.1.2" --index-url https://download.pytorch.org/whl/cu118
RUN pip install --no-cache-dir \
    "fastapi==0.109.0" \
    "uvicorn[standard]==0.27.0" \
    "transformers==4.36.2" \
    "soundfile==0.12.1" \
    "accelerate==0.25.0" \
    "numpy<2.0" # 🔥 KRİTİK FIX: NumPy versiyonunu 1.x serisine sabitliyoruz.

# --- UYGULAMA & MODEL KURULUMU ---
COPY ./app /app/app
ENV MODEL_ID="facebook/mms-tts-tur"
RUN python3 -c "from transformers import VitsModel, AutoTokenizer; AutoTokenizer.from_pretrained('${MODEL_ID}'); VitsModel.from_pretrained('${MODEL_ID}')"

# --- ÇALIŞTIRMA ---
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]