import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import engine, AsyncSessionLocal, Base
from app.camera.manager import camera_manager, get_default_cameras
from app.detection.engine import detection_engine
from app.tracking.engine import tracking_engine
from app.rules.engine import rule_engine
from app.alarm.manager import alarm_manager
from app.redis_client import check_redis_health, close_redis
from app.db import crud
from app.db.crud import upsert_camera
from app.api import cameras, events, websocket, detection, zones, tracking, rules

log = structlog.get_logger()


async def _fps_logger():
    """Her 30 saniyede kamera FPS değerlerini terminale yazar."""
    while True:
        await asyncio.sleep(30)
        for status in camera_manager.get_all_statuses():
            log.info(
                "camera.fps_report",
                camera_id=status.camera_id,
                fps=status.fps,
                connected=status.is_connected,
            )


async def _detection_result_consumer():
    """
    Detection result_queue'dan sonuçları tüketir; Tracking Engine ve Rule
    Engine'i besler.
    Faz 4'te Event Engine bu ihlallerden DB olayı üretecek.
    """
    from app.detection.engine import detection_engine
    while True:
        try:
            result = await asyncio.wait_for(
                detection_engine.result_queue.get(), timeout=2.0
            )
            summary = result.summary()
            # Yalnızca anlamlı tespitler loglanır
            if summary["persons"] > 0 or summary["fire"] or summary["fall"]:
                log.debug(
                    "detection.result",
                    **summary,
                )
            # Yangın/düşme varsa warning seviyesinde logla
            if summary["fire"] or summary["smoke"]:
                log.warning("detection.alert.fire_smoke", camera_id=summary["camera_id"])
            if summary["fall"]:
                log.warning("detection.alert.fall", camera_id=summary["camera_id"])

            # Faz 3: genel tespitleri (person/vehicle) takip et, sonra kural motoruna gönder
            tracked_objects = tracking_engine.update(result.camera_id, result.general)
            rule_engine.evaluate(result.camera_id, tracked_objects)
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            log.error("detection_consumer.error", error=str(exc))


async def _zones_refresher():
    """Zone tanımlarını periyodik olarak DB'den okuyup RuleEngine önbelleğini günceller."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                rule_engine.set_zones(await crud.get_zones_by_camera(db))
        except Exception as exc:
            log.warning("app.zones.refresh_failed", error=str(exc))
        await asyncio.sleep(settings.zones_cache_ttl_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Başlangıç ──────────────────────────────────────────────────────────────
    log.info("app.startup", env=settings.app_env)

    # 1) DB: Tabloları oluştur (yoksa) — Docker'da Alembic, geliştirmede create_all
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("app.db.tables_ready")
    except Exception as e:
        log.warning("app.db.init_failed", error=str(e))

    # 2) Redis bağlantısını doğrula
    redis_ok = await check_redis_health()
    log.info("app.redis.health", ok=redis_ok)

    # 3) Varsayılan kameraları belleğe kaydet
    default_cameras = get_default_cameras()
    camera_manager.register_all(default_cameras)

    # 4) Kameraları DB'ye senkronize et
    try:
        async with AsyncSessionLocal() as db:
            for cam in default_cameras:
                await upsert_camera(db, cam)
        log.info("app.cameras.synced_to_db", count=len(default_cameras))
    except Exception as e:
        log.warning("app.cameras.db_sync_failed", error=str(e))

    # 5) Arkaplan görevleri
    asyncio.create_task(camera_manager.start_all())
    asyncio.create_task(detection_engine.start(camera_manager))
    asyncio.create_task(_detection_result_consumer())
    asyncio.create_task(_fps_logger())
    asyncio.create_task(_zones_refresher())

    yield

    # ── Kapatma ────────────────────────────────────────────────────────────────
    log.info("app.shutdown")
    detection_engine.stop()
    await camera_manager.stop_all()
    await close_redis()


app = FastAPI(
    title="Fabrika Güvenlik Kameraları — AI Platform",
    description="Modüler fabrika güvenlik kamera analizi platformu",
    version="0.2.0",
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
app.include_router(detection.router)
app.include_router(zones.router)
app.include_router(tracking.router)
app.include_router(rules.router)


@app.get("/view", response_class=HTMLResponse, tags=["system"])
async def cameras_view_index():
    """React paneli (Faz 6) hazır olana kadar hızlı görsel doğrulama için:
    tüm kameraları ve canlı tespit akışı linklerini listeler."""
    cameras = camera_manager.list_cameras()
    if cameras:
        items = "".join(
            f'<li><a href="/api/detection/{c.id}/view">{c.name} ({c.id})</a></li>'
            for c in cameras
        )
    else:
        items = "<li>Kayıtlı kamera yok</li>"
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Kameralar — Canlı İzleme</title>
<style>
  body {{ background:#111; color:#eee; font-family:sans-serif; padding:24px; }}
  a {{ color:#4fc3f7; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  li {{ margin:8px 0; font-size:1.1em; }}
</style>
</head>
<body>
  <h2>Kameralar</h2>
  <ul>{items}</ul>
</body>
</html>"""


@app.get("/health", tags=["system"])
async def health():
    # DB sağlık kontrolü
    db_ok = False
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    # Redis sağlık kontrolü
    redis_ok = await check_redis_health()

    overall = "ok" if db_ok else "degraded"
    return {
        "status": overall,
        "version": "0.2.0",
        "env": settings.app_env,
        "cameras": len(camera_manager.list_cameras()),
        "active_ws": alarm_manager.connection_count,
        "services": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "degraded",
        },
    }
