import logging
import grpc
import time
import os
from concurrent import futures
import asyncio

try:
    from sentiric.tts.v1 import mms_pb2
    from sentiric.tts.v1 import mms_pb2_grpc
except ImportError:
    logging.critical("❌ Sentiric Contracts not found or mms.proto missing! gRPC server disabled.")
    mms_pb2 = None
    mms_pb2_grpc = None

from app.core.engine import tts_engine
from app.core.config import settings

logger = logging.getLogger("GRPC-SERVER")

class TtsMmsServicer(mms_pb2_grpc.TtsMmsServiceServicer if mms_pb2_grpc else object):
    
    def MmsSynthesize(self, request, context):
        if not mms_pb2: context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts missing")
        
        start = time.perf_counter()
        try:
            audio_bytes = tts_engine.synthesize(request.text, speed=request.speed or 1.0)
            
            logger.info(f"gRPC Unary handled in {time.perf_counter()-start:.3f}s")
            
            return mms_pb2.MmsSynthesizeResponse(
                audio_content=audio_bytes,
                sample_rate=tts_engine.sampling_rate
            )
        except Exception as e:
            logger.error(f"gRPC Unary Error: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def MmsSynthesizeStream(self, request, context):
        if not mms_pb2: context.abort(grpc.StatusCode.UNIMPLEMENTED, "Contracts missing")
        
        try:
            for chunk in tts_engine.synthesize_stream(request.text, speed=request.speed or 1.0):
                yield mms_pb2.MmsSynthesizeStreamResponse(
                    audio_chunk=chunk,
                    is_final=False
                )
            yield mms_pb2.MmsSynthesizeStreamResponse(audio_chunk=b"", is_final=True)
            
        except Exception as e:
            logger.error(f"gRPC Stream Error: {e}", exc_info=True)
            context.abort(grpc.StatusCode.INTERNAL, str(e))

def load_tls_credentials():
    try:
        with open(settings.TTS_MMS_SERVICE_KEY_PATH, 'rb') as f:
            private_key = f.read()
        with open(settings.TTS_MMS_SERVICE_CERT_PATH, 'rb') as f:
            certificate_chain = f.read()
        with open(settings.GRPC_TLS_CA_PATH, 'rb') as f:
            root_ca = f.read()

        server_credentials = grpc.ssl_server_credentials(
            [(private_key, certificate_chain)],
            root_certificates=root_ca,
            require_client_auth=True
        )
        return server_credentials
    except Exception as e:
        logger.critical(f"🔥 Failed to load TLS certificates: {e}")
        raise e

async def serve_grpc():
    if not mms_pb2_grpc: 
        logger.info("ℹ️ gRPC Server skipped (No contracts or proto definition found).")
        return
    
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    mms_pb2_grpc.add_TtsMmsServiceServicer_to_server(TtsMmsServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    
    # [FIX] Insecure Fallback Logic (MMS)
    use_tls = (
        settings.TTS_MMS_SERVICE_KEY_PATH and os.path.exists(settings.TTS_MMS_SERVICE_KEY_PATH) and
        settings.TTS_MMS_SERVICE_CERT_PATH and os.path.exists(settings.TTS_MMS_SERVICE_CERT_PATH) and
        settings.GRPC_TLS_CA_PATH and os.path.exists(settings.GRPC_TLS_CA_PATH)
    )

    if use_tls:
        try:
            tls_creds = load_tls_credentials()
            server.add_secure_port(listen_addr, tls_creds)
            logger.info(f"🔒 gRPC Server (MMS) starting on {listen_addr} (mTLS Enabled)")
        except Exception:
            logger.error("Failed to initialize secure port, shutting down.")
            return
    else:
        logger.warning(f"⚠️ TLS paths missing or invalid. Starting gRPC Server (MMS) on {listen_addr} (INSECURE)")
        server.add_insecure_port(listen_addr)

    await server.start()
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await server.stop(5)