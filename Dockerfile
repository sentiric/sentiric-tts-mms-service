# 1️⃣ Base Image (CUDA support)
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 2️⃣ System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip python3-venv libsndfile1 git curl \
    && rm -rf /var/lib/apt/lists/*

# 3️⃣ UV Installer (Hızlı pip alternatifi)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 4️⃣ Python Environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN uv venv $VIRTUAL_ENV --python /usr/bin/python3.10

# 5️⃣ Install Torch First (Cache optimization)
RUN uv pip install --no-cache \
    "torch==2.1.2" "torchaudio==2.1.2" \
    --index-url https://download.pytorch.org/whl/cu118

# 6️⃣ Dependencies
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# 7️⃣ Model Bake-in (Build zamanında indir)
# Bu adım, runtime'da indirme beklememek için kritiktir.
ARG MODEL_ID="facebook/mms-tts-tur"
RUN python3 -c "from transformers import AutoTokenizer, VitsModel; \
    AutoTokenizer.from_pretrained('${MODEL_ID}'); \
    VitsModel.from_pretrained('${MODEL_ID}')"

# 8️⃣ Copy Code
COPY . .

# 9️⃣ Ports & Entrypoint
EXPOSE 14060 14061 14062

# 🔟 CMD: Environment variable kullanarak başlatma
# Not: Shell formunda yazıyoruz ki değişkenler expand edilebilsin.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 14060 --no-access-log"]