"""
Streams API — Faz 5 (Gün 17).

HLS canlı yayın durumu ve yönetimi. Segment dosyalarının kendisi Docker'da
nginx (/streams/ location), yerel geliştirmede FastAPI StaticFiles mount'u
(bkz. main.py) ile servis edilir — bu API sadece durum/kontrol içindir.
"""
from fastapi import APIRouter, HTTPException

from app.video.buffer import video_buffer_manager
from app.video.clips import clip_service
from app.video.hls import hls_manager

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.get("")
async def list_streams():
    """Tüm HLS yayınlarının durumunu döndürür. Webcam kameralar HLS yerine
    MJPEG ile izlenir (/api/detection/{id}/stream) ve burada listelenmez."""
    return {
        "hls_enabled": hls_manager.enabled,
        "streams": hls_manager.get_all_statuses(),
    }


@router.get("/video-stats")
async def video_stats():
    """Video alt sistemi durumu: kamera başına ring buffer doluluğu ve
    klip üretim istatistikleri (hızlı teşhis için)."""
    return {
        "buffers": video_buffer_manager.get_stats(),
        "clips": clip_service.get_stats(),
    }


@router.get("/{camera_id}")
async def stream_status(camera_id: str):
    status = hls_manager.get_status(camera_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail="Bu kamera için HLS yayını yok (webcam kameralar MJPEG "
                   "ile izlenir: /api/detection/{camera_id}/stream)",
        )
    return status


@router.post("/{camera_id}/restart")
async def restart_stream(camera_id: str):
    """Takılan/bozulan HLS yayınını elle yeniden başlatır."""
    ok = await hls_manager.restart(camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bu kamera için HLS yayını yok")
    return {"status": "restarted", "camera_id": camera_id}
