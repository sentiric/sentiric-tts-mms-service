import os
import shutil
import glob
import uuid
import logging
import time
import json
import hashlib
import asyncio
from typing import List, Optional, Dict, Any

import torch
import langid
import numpy as np 
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from app.core.engine import tts_engine 
from app.core.config import settings
from app.api.schemas import TTSRequest, OpenAISpeechRequest 
from app.core.history import history_manager
from app.core.audio import audio_processor

logger = logging.getLogger("API")
router = APIRouter()

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

for d in [UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# --- YARDIMCI FONKSİYONLAR ---

async def cleanup_files(file_paths: List[str]):
    for path in file_paths:
        try:
            if os.path.exists(path):
                await asyncio.to_thread(os.remove, path)
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")

def calculate_vca_metrics(start_time, text, audio_bytes, sample_rate):
    process_time = time.perf_counter() - start_time
    len_bytes = len(audio_bytes) if audio_bytes else 0
    audio_duration_sec = len_bytes / (sample_rate * 2) if len_bytes > 0 else 0
    rtf = process_time / audio_duration_sec if audio_duration_sec > 0 else 0
    
    return {
        "X-VCA-Chars": str(len(text)),
        "X-VCA-Time": f"{process_time:.3f}",
        "X-VCA-RTF": f"{rtf:.4f}",
        "X-VCA-Model": settings.MODEL_ID
    }

def generate_deterministic_filename(params: dict, ext: str) -> str:
    key_data = {
        "text": params.get("text"),
        "lang": params.get("language"),
        "speed": params.get("speed"),
        "fmt": ext
    }
    file_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    return f"{file_hash}.{ext}"

# --- SYSTEM ENDPOINTS ---

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")
    
@router.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "device": settings.DEVICE, 
        "model_loaded": tts_engine.model is not None,
        "version": settings.APP_VERSION, 
        "model_id": settings.MODEL_ID,
        "sample_rate": tts_engine.sampling_rate if tts_engine.model else None
    }

@router.get("/api/config")
async def get_public_config():
    langs = [{"code": "tr", "name": "Turkish"}]
    return {
        "app_name": settings.APP_NAME, "version": settings.APP_VERSION,
        "defaults": {
            "speed": settings.DEFAULT_SPEED,
            "language": settings.DEFAULT_LANGUAGE,
            "sample_rate": tts_engine.sampling_rate if tts_engine.model else 16000
        },
        "limits": {
            "max_text_len": 5000, 
            "supported_formats": ["wav", "pcm"], 
            "supported_languages": langs 
        },
        "system": {"streaming_enabled": settings.ENABLE_STREAMING, "device": settings.DEVICE}
    }

# --- OPENAI COMPATIBLE ENDPOINTS ---

@router.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [
        {"id": "mms-tur", "object": "model", "name": "Sentiric MMS Turkish"},
        {"id": "tts-1", "object": "model", "name": "Sentiric TTS (Fallback)"}
    ]}

@router.post("/v1/audio/speech")
async def openai_speech_endpoint(request: OpenAISpeechRequest):
    if not request.input or not request.input.strip(): 
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")
    
    # HATA DÜZELTME: Şemada language alanı opsiyonel olsa bile kontrol et
    lang_code = "tr"
    if hasattr(request, "language") and request.language:
        lang_code = request.language.lower()
        
    output_fmt = "wav" 
    
    logger.info(f"OpenAI TTS: '{request.input[:15]}...' -> ({lang_code})")

    try:
        audio_bytes = await asyncio.to_thread(
            tts_engine.synthesize, 
            request.input, 
            request.speed
        )
        
        media_type = "audio/wav"
        if request.response_format == "mp3":
            media_type = "audio/mpeg" # MP3 istenirse header'ı ayarla (içerik wav kalsa bile client genelde çalar)
             
        return Response(content=audio_bytes, media_type=media_type)
        
    except Exception as e:
        logger.error(f"OpenAI TTS Endpoint Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- INTERNAL API ENDPOINTS ---

@router.get("/api/speakers")
async def get_speakers():
    return {"speakers": {"default": ["neutral"]}}

@router.post("/api/speakers/refresh")
async def refresh_speakers_cache():
    return {"status": "info", "message": "MMS model has fixed speakers."}

@router.get("/api/history")
async def get_history(): 
    return history_manager.get_all()

@router.get("/api/history/audio/{filename}")
async def get_history_audio(filename: str):
    file_path = os.path.join(HISTORY_DIR, os.path.basename(filename))
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="History audio not found")

@router.delete("/api/history/all")
async def delete_all_history():
    history_manager.clear_all()
    for f in glob.glob(os.path.join(HISTORY_DIR, "*")):
        if os.path.isfile(f):
            try: os.remove(f)
            except: pass
    return {"status": "cleared"}

@router.delete("/api/history/{filename}")
async def delete_history_entry(filename: str):
    safe_filename = os.path.basename(filename)
    history_manager.delete_entry(safe_filename)
    try: os.remove(os.path.join(HISTORY_DIR, safe_filename))
    except: pass
    return {"status": "deleted"}

@router.post("/api/tts")
async def generate_speech(request: TTSRequest):
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    
    params = request.dict(exclude_unset=True)
    start_time = time.perf_counter()
    
    if request.stream:
        logger.info("Stream request received. Starting pseudo-streaming synthesis.")
        
        async def stream_and_save():
            accumulated_bytes = bytearray()
            safe_filename = generate_deterministic_filename(params, "pcm") 
            filepath = os.path.join(HISTORY_DIR, safe_filename)
            
            try:
                # HATA DÜZELTME: 'async for' YERİNE 'for'
                # tts_engine.synthesize_stream senkron bir jeneratördür.
                # await kullanmadan doğrudan iterate ediyoruz.
                # FastAPI StreamingResponse threadpool'da çalışacağı için bloklama minimaldir.
                for chunk in tts_engine.synthesize_stream(request.text, request.speed):
                    if chunk:
                        accumulated_bytes.extend(chunk)
                        yield chunk
                        # Diğer tasklara fırsat vermek için küçük bir sleep (opsiyonel)
                        await asyncio.sleep(0) 
            except Exception as e:
                 logger.error(f"Streaming error: {e}")
            finally:
                if accumulated_bytes:
                    wav_bytes = audio_processor.numpy_to_wav_bytes(
                        np.frombuffer(bytes(accumulated_bytes), dtype=np.int16),
                        tts_engine.sampling_rate
                    )
                    if wav_bytes:
                        await asyncio.to_thread(open(filepath, "wb").write, wav_bytes)
                        history_manager.add_entry(
                            filename=safe_filename.replace(".pcm", ".wav"), 
                            text=request.text, language=request.language,
                            speaker=request.speaker_idx, mode="Stream"
                        )
        
        return StreamingResponse(stream_and_save(), media_type="application/octet-stream")
        
    else: # Unary Request
        # HATA DÜZELTME: Şema güncellendiği için output_format artık mevcut
        ext = request.output_format if request.output_format in ["wav", "pcm"] else "wav"
        media_type = "audio/wav" if ext == "wav" else "application/octet-stream"
        
        safe_filename = generate_deterministic_filename(params, ext)
        
        # Cache implementasyonu engine içinde var
        audio_bytes = await asyncio.to_thread(tts_engine.synthesize, request.text, request.speed)
        
        metrics = calculate_vca_metrics(start_time, request.text, audio_bytes, tts_engine.sampling_rate)
        return Response(content=audio_bytes, media_type=media_type, headers=metrics)