import logging
import grpc
import time
from concurrent import futures
import asyncio

# Contract Import (Soft Fail Korumalı)
try:
    # MMS için yeni proto tanımını import et
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
            # Gelen language_code'u şimdilik yoksayıyoruz, model sabit
            audio_bytes = tts_engine.synthesize(request.text, speed=request.speed or 1.0)
            
            logger.info(f"gRPC Unary handled in {time.perf_counter()-start:.3f}s")
            
            return mms_pb2.MmsSynthesizeResponse(
                audio_content=audio_bytes,
                sample_rate=tts_engine.sampling_rate # Modelden alınan sample rate
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
                    is_final=False # Her parça için false
                )
            # Akış bittiğinde son bir 'is_final=true' mesajı gönder
            yield mms_pb2.MmsSynthesizeStreamResponse(audio_chunk=b"", is_final=True)
            
        except Exception as e:
            logger.error(f"gRPC Stream Error: {e}", exc_info=True)
            # Akış hatasında istemciye bilgi ver
            context.abort(grpc.StatusCode.INTERNAL, str(e))

async def serve_grpc():
    if not mms_pb2_grpc: 
        logger.info("ℹ️ gRPC Server skipped (No contracts or proto definition found).")
        return
    
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=4))
    mms_pb2_grpc.add_TtsMmsServiceServicer_to_server(TtsMmsServicer(), server)
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    logger.info(f"🚀 gRPC Server (MMS) starting on {listen_addr}")
    await server.start()
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await server.stop(5)