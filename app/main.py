import logging
import shutil
import os
import asyncio
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.engine import tts_engine # Engine singleton olarak başlatıldı
from app.api.endpoints import router as api_router
from app.core.logging_utils import setup_logging
from app.core.config import settings
from app.grpc_server import serve_grpc

setup_logging()
logger = logging.getLogger("APP")

UPLOAD_DIR = "/app/uploads"
HISTORY_DIR = "/app/history"
CACHE_DIR = "/app/cache"

# Dizinlerin varlığından emin ol
for d in [UPLOAD_DIR, HISTORY_DIR, CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENV} | Device: {settings.DEVICE}")
    
    if settings.API_KEY:
        logger.info("🔒 SECURITY: Standalone API Key protection ENABLED.")
    else:
        logger.info("🔓 SECURITY: Running in Open/Gateway Mode (No internal auth).")

    # 1. Motoru Başlat (Singleton olduğu için ilk çağrıda initialize olur)
    try:
        if not tts_engine.model: tts_engine.initialize() # Eğer değilse başlat
    except Exception as e:
        logger.critical(f"🔥 CRITICAL: Engine failed to initialize: {e}")
        # FastAPI bu hatayı yakalayıp uygulamayı durduracak
        raise RuntimeError("Engine initialization failed") from e

    # 2. gRPC Sunucusunu Arka Planda Başlat
    grpc_task = asyncio.create_task(serve_grpc())
    
    yield
    
    logger.info("🛑 Shutting down...")
    grpc_task.cancel()
    
    # Cleanup (opsiyonel, container kapatılırken yapılabilir)
    # shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    # logger.info("🧹 Uploads cleaned.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None, # Sadece dev'de docs
    redoc_url=None
)

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Coqui uyumluluğu için bu header'ları expose et
    expose_headers=["X-VCA-Chars", "X-VCA-Time", "X-VCA-RTF", "X-Model", "X-Cache", "X-Trace-ID"] 
)

# --- ROUTING ---
app.include_router(api_router)

# --- Root Endpoint ---
@app.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} Service",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.ENV != "production" else "API Docs disabled in production"
    }

# --- HEALTH CHECK (FastAPI lifespan'dan sonra daha doğru bilgi verir) ---
# Bu endpoint, `/health` route'u zaten api_router'da tanımlandığı için kaldırıldı.
# Gerekirse tekrar eklenebilir.