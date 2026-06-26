import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.camera.manager import camera_manager, get_default_cameras
from app.detection.engine import detection_engine
from app.api import cameras, events, websocket

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Başlangıç ──────────────────────────────────────────────────────────────
    log.info("app.startup", env=settings.app_env)

    # Varsayılan kameraları kaydet (Faz 0: laptop webcam)
    camera_manager.register_all(get_default_cameras())

    # Kamera akışlarını başlat
    import asyncio
    asyncio.create_task(camera_manager.start_all())

    # Detection engine (şu an Faz 0 iskeleti)
    asyncio.create_task(detection_engine.start(camera_manager.frame_queue))

    yield

    # ── Kapatma ────────────────────────────────────────────────────────────────
    log.info("app.shutdown")
    detection_engine.stop()
    await camera_manager.stop_all()


app = FastAPI(
    title="Fabrika Güvenlik Kameraları — AI Platform",
    description="Modüler fabrika güvenlik kamera analizi platformu",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrikleri
Instrumentator().instrument(app).expose(app)

# Rotalar
app.include_router(cameras.router)
app.include_router(events.router)
app.include_router(websocket.router)


@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "cameras": len(camera_manager.list_cameras()),
        "active_ws": 0,  # Faz 5'te alarm_manager.connection_count
    }
