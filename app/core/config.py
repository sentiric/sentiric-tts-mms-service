import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- APP INFO ---
    APP_NAME: str = "Sentiric MMS TTS Pro"
    APP_VERSION: str = "1.2.0-stable"
    ENV: str = os.getenv("ENV", "production")
    
    # --- NETWORK & SECURITY ---
    HOST: str = "0.0.0.0"
    HTTP_PORT: int = int(os.getenv("TTS_MMS_SERVICE_HTTP_PORT", "14060"))
    GRPC_PORT: int = int(os.getenv("TTS_MMS_SERVICE_GRPC_PORT", "14061"))
    METRICS_PORT: int = int(os.getenv("TTS_MMS_SERVICE_METRICS_PORT", "14062"))
    
    CORS_ORIGINS: List[str] = os.getenv("TTS_MMS_SERVICE_CORS_ORIGINS", "*").split(",")
    API_KEY: Optional[str] = os.getenv("TTS_MMS_SERVICE_API_KEY", None)

    # --- MODEL & SYSTEM ---
    MODEL_ID: str = os.getenv("TTS_MMS_SERVICE_MODEL_ID", "facebook/mms-tts-tur")
    DEVICE: str = os.getenv("TTS_MMS_SERVICE_DEVICE", "cuda").strip().lower()
    
    # --- INFERENCE DEFAULTS ---
    DEFAULT_LANGUAGE: str = "tur"
    DEFAULT_SPEED: float = float(os.getenv("TTS_MMS_SERVICE_DEFAULT_SPEED", "1.0"))
    # MMS modelleri genellikle 16kHz (VITS) veya 24kHz olabilir. Model config'den okunacak ama default bu.
    DEFAULT_SAMPLE_RATE: int = int(os.getenv("TTS_MMS_SERVICE_DEFAULT_SAMPLE_RATE", "16000")) 

    # --- LOGGING ---
    DEBUG: bool = os.getenv("TTS_MMS_SERVICE_DEBUG", "false").lower() == "true"

settings = Settings()