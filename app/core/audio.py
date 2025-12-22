import logging
import io
import torch
import soundfile as sf
import numpy as np

logger = logging.getLogger("AUDIO-PROC")

class AudioProcessor:
    @staticmethod
    def process_waveform(waveform: np.ndarray) -> np.ndarray:
        """
        Ham model çıktısını normalize eder ve kırpmayı (clipping) önler.
        MMS VITS çıktısı bazen [-1, 1] aralığını taşabilir.
        """
        # NaN veya Infinite kontrolü
        if not np.isfinite(waveform).all():
            logger.warning("Waveform contains NaN or Inf! Replacing with silence.")
            return np.zeros_like(waveform)

        # Normalizasyon (Peak Normalization)
        max_val = np.max(np.abs(waveform))
        if max_val > 1.0:
            waveform = waveform / max_val
        
        return waveform

    @staticmethod
    def numpy_to_wav_bytes(waveform: np.ndarray, sample_rate: int) -> bytes:
        """NumPy array'i geçerli bir RIFF WAV dosyasına dönüştürür."""
        try:
            waveform = AudioProcessor.process_waveform(waveform)
            
            buffer = io.BytesIO()
            # subtype='PCM_16' en uyumlu formattır. Float32 çoğu playerda çalışmaz.
            sf.write(buffer, waveform, sample_rate, format='WAV', subtype='PCM_16')
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logger.error(f"WAV conversion failed: {e}")
            return b""

    @staticmethod
    def float32_to_pcm16(waveform: np.ndarray) -> bytes:
        """Streaming için ham PCM byte'ları (Header yok)."""
        try:
            waveform = AudioProcessor.process_waveform(waveform)
            # 16-bit integer dönüşümü
            pcm_data = (waveform * 32767).astype(np.int16)
            return pcm_data.tobytes()
        except Exception as e:
            logger.error(f"PCM conversion failed: {e}")
            return b""

audio_processor = AudioProcessor()