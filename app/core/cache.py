import os
import hashlib
import json
import logging
from typing import List, Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger("CACHE")

class TtsEngineCache:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TtsEngineCache, cls).__new__(cls)
            cls._instance.cache_dir = "/app/cache"
            cls._instance.cache_file_ext = "wav" # Varsayılan olarak WAV
            os.makedirs(cls._instance.cache_dir, exist_ok=True)
        return cls._instance

    def _generate_cache_key(self, text: str, language: str, speed: float) -> str:
        """Cache için benzersiz ve deterministik bir anahtar üretir."""
        key_data = {
            "text": text,
            "lang": language,
            "speed": speed,
            "model": settings.MODEL_ID # Model bazlı cacheleme için
        }
        # JSON dump ve hash ile anahtar oluşturma
        cache_key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
        return f"{cache_key}.{self.cache_file_ext}"

    def get_cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, key)

    def exists(self, key: str) -> bool:
        return os.path.exists(self.get_cache_path(key))

    def save(self, key: str, audio_bytes: bytes) -> None:
        """Sentezlenen sesi cache'e kaydeder."""
        try:
            with open(self.get_cache_path(key), "wb") as f:
                f.write(audio_bytes)
            logger.debug(f"Saved cache for key: {key}")
        except Exception as e:
            logger.warning(f"Failed to save cache for key {key}: {e}")

    def load(self, key: str) -> Optional[bytes]:
        """Cache'den sesi yükler."""
        try:
            if self.exists(key):
                with open(self.get_cache_path(key), "rb") as f:
                    logger.debug(f"Cache HIT for key: {key}")
                    return f.read()
            logger.debug(f"Cache MISS for key: {key}")
            return None
        except Exception as e:
            logger.warning(f"Failed to load cache for key {key}: {e}")
            return None

tts_cache = TtsEngineCache() # Singleton instance