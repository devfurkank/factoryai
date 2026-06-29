"""
Detection API — Model durumu ve tespit istatistikleri.
"""
from fastapi import APIRouter
from app.detection.engine import detection_engine

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.get("/status")
async def detection_status():
    """Detection engine ve yüklü model durumunu döndürür."""
    return {
        "ready": detection_engine.is_ready,
        **detection_engine.get_stats(),
    }
