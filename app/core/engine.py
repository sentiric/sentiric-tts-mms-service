import torch
import numpy as np
import logging
import threading
import re
import time
import hashlib
import json
from typing import Generator, Optional, Dict, List

from transformers import VitsModel, AutoTokenizer
from app.core.config import settings
from app.core.audio import audio_processor
from app.core.history import history_manager
from app.core.cache import tts_cache

logger = logging.getLogger("MMS-ENGINE")

class MmsEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MmsEngine, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.tokenizer = None
            cls._instance.device = settings.DEVICE
            cls._instance.sampling_rate = settings.DEFAULT_SAMPLE_RATE
            cls._instance.model_config = None
            cls._instance.cache_file_ext = "wav" # Caching için kullanılacak uzantı
        return cls._instance

    def initialize(self):
        if not self.model:
            logger.info(f"🚀 Initializing MMS Engine... Device: {self.device}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(settings.MODEL_ID)
                self.model = VitsModel.from_pretrained(settings.MODEL_ID).to(self.device)
                self.model.eval()
                
                self.sampling_rate = getattr(self.model.config, 'sampling_rate', 16000)
                logger.info(f"✅ MMS Model Loaded: {settings.MODEL_ID} | SR: {self.sampling_rate}Hz")
            except Exception as e:
                logger.critical(f"🔥 Model init failed: {e}", exc_info=True)
                raise e

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]
        
    def _generate_cache_key(self, text: str, language: str, speed: float) -> str:
        """Cache için benzersiz ve deterministik bir anahtar oluşturur."""
        key_data = {
            "text": text,
            "lang": language,
            "speed": speed,
            "model": settings.MODEL_ID 
        }
        cache_key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
        return f"{cache_key}.{self.cache_file_ext}"

    def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        if not text.strip(): return b""
        
        cleaned_text = self._clean_text(text)
        cache_key = self._generate_cache_key(cleaned_text, settings.DEFAULT_LANGUAGE, speed)

        # 1. Cache kontrolü
        cached_audio = tts_cache.load(cache_key)
        if cached_audio:
            logger.info(f"Cache HIT for key: {cache_key[:8]}...")
            return cached_audio
            
        logger.info(f"Cache MISS for key: {cache_key[:8]}...")
        # 2. Caching yoksa sentezle
        with self._lock:
            try:
                inputs = self.tokenizer(cleaned_text, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    output = self.model(**inputs).waveform
                
                waveform_np = output.cpu().numpy().squeeze()
                audio_bytes = audio_processor.numpy_to_wav_bytes(waveform_np, self.sampling_rate)
                
                # 3. Sonucu cache'e kaydet
                tts_cache.save(cache_key, audio_bytes)
                
                # 4. History'ye ekle
                history_manager.add_entry(
                    filename=cache_key, text=text, language=settings.DEFAULT_LANGUAGE,
                    speaker=None, # MMS'te speaker seçimi yok
                    mode="Standard"
                )
                
                if self.device == "cuda": torch.cuda.empty_cache()
                return audio_bytes
                
            except Exception as e:
                logger.error(f"Synthesis failed for text '{text[:30]}...': {e}", exc_info=True)
                raise e

    def synthesize_stream(self, text: str, speed: float = 1.0) -> Generator[bytes, None, None]:
        sentences = self._split_sentences(text)
        if not sentences: return
        
        # Stream cache'lenmez. Her cümle ayrı üretilir.
        for i, sentence in enumerate(sentences):
            if not sentence.strip(): continue
            
            with self._lock:
                try:
                    inputs = self.tokenizer(sentence, return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        output = self.model(**inputs).waveform
                    
                    waveform_np = output.cpu().numpy().squeeze()
                    pcm_bytes = audio_processor.float32_to_pcm16(waveform_np)
                    
                    if len(pcm_bytes) > 0:
                        yield pcm_bytes
                        # History'ye ilk cümlenin kaydı eklenebilir (opsiyonel)
                        if i == 0:
                           history_manager.add_entry(
                                filename=f"stream_{hashlib.md5(text.encode()).hexdigest()}.pcm",
                                text=text, language=settings.DEFAULT_LANGUAGE,
                                speaker=None, mode="Stream"
                           )
                        
                except Exception as e:
                    logger.error(f"Stream synthesis error for sentence '{sentence[:30]}...': {e}", exc_info=True)
                    continue
                finally:
                    if self.device == "cuda": torch.cuda.empty_cache()

# Singleton instance
tts_engine = MmsEngine()