from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from app.core.config import settings

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Sentezlenecek metin veya SSML")
    language: Optional[str] = Field(default=settings.DEFAULT_LANGUAGE, description="Dil kodu (ISO 639-1)")
    speed: Optional[float] = Field(default=settings.DEFAULT_SPEED, ge=0.5, le=2.0, description="Konuşma hızı (1.0 varsayılan)")
    stream: Optional[bool] = Field(default=False, description="Parçalı (chunked) yanıt için")
    # EKLENDİ: Eksik olan output_format alanı
    output_format: Optional[str] = Field(default="wav", description="Çıktı formatı: wav, pcm")
    
    # --- Coqui API Uyumluluk Alanları (MMS için args olarak geçirilecek veya yoksayılacak) ---
    speaker_idx: Optional[str] = Field(None, description="Konuşmacı (MMS için önemsiz)")
    temperature: Optional[float] = Field(None, description="Sampling temperature (MMS için yok)")
    top_k: Optional[int] = Field(None, description="Top-K sampling (MMS için yok)")
    top_p: Optional[float] = Field(None, description="Top-P sampling (MMS için yok)")
    
    # --- Modelin desteklediği sample rate'i belirtmek için ---
    sample_rate: Optional[int] = Field(default=None)

    @validator('language')
    def validate_language(cls, value):
        if value and value.lower() not in ["tur", "tr"]:
            # Sadece Türkçe destekleniyor uyarısı (loglamak yeterli, hata fırlatmayalım)
            pass
        return value.lower() if value else settings.DEFAULT_LANGUAGE

class OpenAISpeechRequest(BaseModel):
    model: str = Field("tts-1", description="Model adı (yoksayılır)")
    input: str = Field(..., description="Okunacak metin")
    voice: str = Field("alloy", description="Ses ID'si (Sentiric'teki ID'lere map edilir)")
    response_format: str = Field("mp3", description="mp3, opus, aac, flac, wav, pcm")
    speed: float = Field(1.0, ge=0.25, le=4.0)
    
    # EKLENDİ: OpenAI standartlarında olmasa da kodun beklediği dil alanı
    language: Optional[str] = Field(default="tr", description="Dil kodu (Standart dışı ek)")