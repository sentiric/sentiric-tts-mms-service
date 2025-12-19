import os
import io
from contextlib import asynccontextmanager
from typing import Optional

import torch
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from transformers import VitsModel, AutoTokenizer

# --- Globals ---
class AppState:
    model: Optional[VitsModel] = None
    tokenizer: Optional[AutoTokenizer] = None

app_state = AppState()
MODEL_ID = os.getenv("MODEL_ID", "facebook/mms-tts-tur")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Sunucu başlıyor... Cihaz: {DEVICE}")
    print(f"⏳ Modeli yüklüyor: {MODEL_ID}")
    try:
        app_state.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        app_state.model = VitsModel.from_pretrained(MODEL_ID).to(DEVICE)
        print("✅ MMS Modeli başarıyla yüklendi.")
    except Exception as e:
        print(f"❌ KRİTİK HATA: Model yüklenemedi. {e}")
    yield
    print("🛑 Sunucu kapanıyor...")
    app_state.model = None
    app_state.tokenizer = None
    torch.cuda.empty_cache()

app = FastAPI(title="Sentiric MMS Service", lifespan=lifespan)

# --- Schema ---
class TTSRequest(BaseModel):
    text: str

# --- Endpoint ---
@app.post("/stream")
async def stream_speech(request: TTSRequest):
    if app_state.model is None or app_state.tokenizer is None:
        raise HTTPException(status_code=503, detail="MMS modeli hazır değil.")

    try:
        inputs = app_state.tokenizer(request.text, return_tensors="pt").to(DEVICE)
        
        with torch.no_grad():
            output = app_state.model(**inputs).waveform
        
        waveform = output.cpu().numpy().squeeze()
        buffer = io.BytesIO()
        sf.write(buffer, waveform, samplerate=app_state.model.config.sampling_rate, format='WAV')
        buffer.seek(0)

        async def stream_generator(data: bytes, chunk_size: int = 4096):
            total_size = len(data)
            for i in range(0, total_size, chunk_size):
                yield data[i:i + chunk_size]

        return StreamingResponse(stream_generator(buffer.getvalue()), media_type="audio/wav")
    except Exception as e:
        print(f"STREAMING ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))