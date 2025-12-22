import os
import grpc
import logging
import time
import numpy as np
import soundfile as sf # WAV kaydetmek için
import io

# Contract Import (MMS için)
try:
    from sentiric.tts.v1 import mms_pb2
    from sentiric.tts.v1 import mms_pb2_grpc
except ImportError:
    logging.critical("❌ Sentiric Contracts not found or mms.proto missing! Cannot run gRPC client.")
    exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("TEST-CLIENT")

def run_test():
    # Varsayılan değerler veya ortam değişkenlerinden alınır
    TARGET_HOST = os.getenv("TTS_SERVICE_HOST", "localhost")
    TARGET_PORT = os.getenv("TTS_SERVICE_PORT", "14061") # MMS gRPC portu
    TARGET_ADDRESS = f"{TARGET_HOST}:{TARGET_PORT}"
    
    OUTPUT_DIR = "/tmp/sentiric-tts-tests"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    OUTPUT_FILE_UNARY = os.path.join(OUTPUT_DIR, "grpc_mms_test.wav")
    OUTPUT_FILE_STREAM = os.path.join(OUTPUT_DIR, "grpc_mms_stream_test.wav")

    logger.info(f"Connecting to gRPC Service at: {TARGET_ADDRESS}")
    try:
        # --- UNARY TEST ---
        with grpc.insecure_channel(TARGET_ADDRESS) as channel:
            stub = mms_pb2_grpc.TtsMmsServiceStub(channel)
            
            request_unary = mms_pb2.MmsSynthesizeRequest(
                text="gRPC ile unary test başarılı.",
                language_code="tur", # MMS için geçerli dil
                speed=1.0
            )
            
            logger.info("Sending MmsSynthesize Request...")
            start_time = time.perf_counter()
            response_unary = stub.MmsSynthesize(request_unary)
            duration = time.perf_counter() - start_time
            logger.info(f"Unary Response Received in {duration:.3f}s | Sample Rate: {response_unary.sample_rate}")

            if len(response_unary.audio_content) < 1000:
                logger.error("❌ gRPC Unary response audio is empty or too short!")
            else:
                with open(OUTPUT_FILE_UNARY, "wb") as f:
                    f.write(response_unary.audio_content)
                logger.info(f"✅ Unary audio saved to: {OUTPUT_FILE_UNARY}")

        # --- STREAMING TEST ---
        with grpc.insecure_channel(TARGET_ADDRESS) as channel:
            stub = mms_pb2_grpc.TtsMmsServiceStub(channel)
            
            request_stream = mms_pb2.MmsSynthesizeStreamRequest(
                text="Bu bir gRPC streaming testidir. Parçalı ses akışı.",
                language_code="tur",
                speed=1.1
            )
            
            logger.info("Sending MmsSynthesizeStream Request...")
            start_time = time.perf_counter()
            response_stream = stub.MmsSynthesizeStream(request_stream)
            
            all_chunks = bytearray()
            chunk_count = 0
            
            # Stream'den gelen parçaları birleştir
            for response_chunk in response_stream:
                if response_chunk.audio_chunk:
                    all_chunks.extend(response_chunk.audio_chunk)
                    chunk_count += 1
                if response_chunk.is_final:
                    logger.info(f"Stream finished after {chunk_count} chunks.")
                    break
            
            duration = time.perf_counter() - start_time
            logger.info(f"Stream Response Received in {duration:.3f}s")

            if len(all_chunks) < 1000:
                logger.error("❌ gRPC Stream response audio is empty or too short!")
            else:
                # Gelen PCM verisini WAV'a çevirip kaydet
                # PCM 16-bit varsayımıyla
                try:
                    pcm_data = np.frombuffer(bytes(all_chunks), dtype=np.int16)
                    # Burada sample rate'i bilmemiz lazım, engine'dan alınmalı
                    # Bu test için hardcoded 16000 kullanılıyor, engine'dan alınmalı
                    actual_sample_rate = 16000 
                    with open(OUTPUT_FILE_STREAM, "wb") as f:
                        # Helper fonksiyonu kullan (eğer varsa) veya direkt sf.write
                        # sf.write(f, pcm_data, actual_sample_rate, format='WAV', subtype='PCM_16')
                        
                        # Placeholder - Gerçek WAV conversion logic burada olmalı (audio_processor?)
                        # Şu an için ham PCM'i direkt kaydediyoruz, bu oynatılamaz olabilir.
                        # Eğer audio_processor kullanılacaksa, o metodun doğru olması şart.
                        f.write(bytes(all_chunks)) 
                    
                    logger.info(f"✅ Stream audio saved to: {OUTPUT_FILE_STREAM}")
                except Exception as audio_err:
                    logger.error(f"Failed to process/save stream audio: {audio_err}")

    except grpc.RpcError as e:
        logger.error(f"gRPC Error: {e.code()} - {e.details()}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected Error: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    run_test()