"""
Detection API — Model durumu ve tespit istatistikleri.
"""
import cv2
from fastapi import APIRouter, HTTPException, Response

from app.detection.engine import detection_engine, annotate_frame
from app.detection.types import BBox

router = APIRouter(prefix="/api/detection", tags=["detection"])


def _bbox_to_dict(b: BBox) -> dict:
    return {
        "x1": round(b.x1, 1),
        "y1": round(b.y1, 1),
        "x2": round(b.x2, 1),
        "y2": round(b.y2, 1),
        "confidence": round(b.confidence, 3),
        "class_name": b.class_name,
    }


@router.get("/status")
async def detection_status():
    """Detection engine ve yüklü model durumunu döndürür."""
    return {
        "ready": detection_engine.is_ready,
        **detection_engine.get_stats(),
    }


@router.get("/{camera_id}/result")
async def detection_latest_result(camera_id: str):
    """Belirtilen kameranın en son işlenmiş tespit sonucunu (kutular + özet)
    JSON olarak döndürür. RTSP/webcam fark etmeksizin her kamera için ayrı
    tutulur — bir kamerada tespit gerçekten çalışıp çalışmadığını buradan
    sayısal olarak doğrulayabilirsiniz."""
    result = detection_engine.get_latest_result(camera_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Bu kamera için henüz işlenmiş bir frame yok (kamera bağlı değil veya henüz ilk batch işlenmedi)",
        )
    return {
        "camera_id": result.camera_id,
        "timestamp": result.timestamp,
        "summary": result.summary(),
        "general": [_bbox_to_dict(b) for b in result.general],
        "ppe": [_bbox_to_dict(b) for b in result.ppe],
        "fire_smoke": [_bbox_to_dict(b) for b in result.fire_smoke],
        "poses": [
            {
                "bbox": _bbox_to_dict(p.bbox),
                "fall_state": p.fall_state.value,
                "body_angle": round(p.body_angle, 1),
            }
            for p in result.poses
        ],
    }


@router.get("/{camera_id}/snapshot")
async def detection_snapshot(camera_id: str):
    """Belirtilen kameranın en son frame'ini, tespit kutuları (person, helmet,
    no_hardhat, fire/smoke, düşme durumu) çizilmiş şekilde JPEG olarak döndürür.
    Tarayıcıda doğrudan açılabilir: /api/detection/{camera_id}/snapshot"""
    result = detection_engine.get_latest_result(camera_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Bu kamera için henüz işlenmiş bir frame yok (kamera bağlı değil veya henüz ilk batch işlenmedi)",
        )
    annotated = annotate_frame(result)
    ok, buffer = cv2.imencode(".jpg", annotated)
    if not ok:
        raise HTTPException(status_code=500, detail="JPEG encode başarısız")
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
