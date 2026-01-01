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
            cls._instance.cache_file_ext = "wav"
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
        # Metin temizliği
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()

    def _split_sentences(self, text: str) -> List[str]:
        # [FIX] Daha sağlam bölme
        # Noktalama işaretlerine göre böl ama onları da tut (lookbehind)
        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        
        valid_sentences = []
        for s in raw_sentences:
            s = s.strip()
            # [CRITICAL FIX] En az bir HARF veya RAKAM içermeli.
            # Sadece noktalama (., !, ?) veya sembol varsa atla.
            if s and re.search(r'[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]', s):
                valid_sentences.append(s)
            else:
                logger.debug(f"Skipping non-speech segment: '{s}'")
        
        return valid_sentences

    def _generate_cache_key(self, text: str, language: str, speed: float) -> str:
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

        # Cache kontrolü
        cached_audio = tts_cache.load(cache_key)
        if cached_audio:
            logger.info(f"Cache HIT for key: {cache_key[:8]}...")
            return cached_audio
            
        logger.info(f"Cache MISS for key: {cache_key[:8]}...")
        
        with self._lock:
            try:
                # [FIX] return_tensors='pt' PyTorch tensörü döndürür.
                inputs = self.tokenizer(cleaned_text, return_tensors="pt").to(self.device)
                
                # [FIX] MMS VITS modeli input_ids'i LongTensor bekler. CPU'da bazen Float gelebilir, garantiye alalım.
                # Ancak tokenizer zaten LongTensor döner. Sorun muhtemelen stream kısmındaydı.
                # Yine de burada da kontrol etmekte fayda var.
                
                with torch.no_grad():
                    output = self.model(**inputs).waveform
                
                waveform_np = output.cpu().numpy().squeeze()
                audio_bytes = audio_processor.numpy_to_wav_bytes(waveform_np, self.sampling_rate)
                
                tts_cache.save(cache_key, audio_bytes)
                history_manager.add_entry(
                    filename=cache_key, text=text, language=settings.DEFAULT_LANGUAGE,
                    speaker=None, mode="Standard"
                )
                
                if self.device == "cuda": torch.cuda.empty_cache()
                return audio_bytes
                
            except Exception as e:
                logger.error(f"Synthesis failed for text '{text[:30]}...': {e}", exc_info=True)
                raise e

    def synthesize_stream(self, text: str, speed: float = 1.0) -> Generator[bytes, None, None]:
        # [FIX] Metni temizle (Gereksiz sembolleri at)
        # Örn: "!Merhaba" -> "Merhaba"
        clean_text = re.sub(r'^[\W_]+', '', text) 
        
        sentences = self._split_sentences(clean_text)
        if not sentences: return
        
        for i, sentence in enumerate(sentences):
            if not sentence.strip(): continue
            
            with self._lock:
                try:
                    inputs = self.tokenizer(sentence, return_tensors="pt").to(self.device)
                    # [Safety] Input size kontrolü (Yine de ekleyelim)
                    if inputs['input_ids'].size(1) == 0:
                        logger.warning(f"Skipping empty tensor for: '{sentence}'")
                        continue

                    with torch.no_grad():
                        output = self.model(**inputs).waveform
                    
                    waveform_np = output.cpu().numpy().squeeze()
                    pcm_bytes = audio_processor.float32_to_pcm16(waveform_np)
                    
                    if len(pcm_bytes) > 0:
                        yield pcm_bytes
                        if i == 0:
                           history_manager.add_entry(
                                filename=f"stream_{hashlib.md5(text.encode()).hexdigest()}.pcm",
                                text=text, language=settings.DEFAULT_LANGUAGE,
                                speaker=None, mode="Stream"
                           )
                        
                except Exception as e:
                    # Hata olsa bile stream'i koparma, logla ve devam et
                    logger.error(f"Stream synthesis error for sentence '{sentence}': {e}", exc_info=False)
                    continue
                finally:
                    if self.device == "cuda": torch.cuda.empty_cache()

tts_engine = MmsEngine()