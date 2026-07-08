"""
Detection API — Model durumu, tespit istatistikleri ve canlı MJPEG yayını.
"""
import asyncio
import html
from typing import List
from urllib.parse import quote

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from app.detection.engine import detection_engine, annotate_frame
from app.detection.types import BBox
from app.rules.engine import rule_engine
from app.rules.geometry import scale_points
from app.rules.types import ZoneData

router = APIRouter(prefix="/api/detection", tags=["detection"])

_STREAM_FPS = 12
_RISK_COLORS = {"high": (0, 0, 255), "medium": (0, 165, 255), "low": (0, 220, 220)}


def _bbox_to_dict(b: BBox) -> dict:
    return {
        "x1": round(b.x1, 1),
        "y1": round(b.y1, 1),
        "x2": round(b.x2, 1),
        "y2": round(b.y2, 1),
        "confidence": round(b.confidence, 3),
        "class_name": b.class_name,
        "track_id": b.track_id,
    }


def _draw_zones(frame: np.ndarray, zones: List[ZoneData]) -> np.ndarray:
    """Poligon bölgelerini (risk seviyesine göre renkli) frame üzerine çizer —
    canlı yayında Rule Engine'in hangi bölgeleri izlediğini görsel olarak
    doğrulamak için. Normalize (0-1) poligonlar frame boyutuna ölçeklenir."""
    frame_size = frame.shape[:2]
    overlay = None
    for zone in zones:
        if not zone.polygon or len(zone.polygon) < 3:
            continue
        polygon_px = scale_points(zone.polygon, frame_size)
        pts = np.array(polygon_px, dtype=np.int32).reshape((-1, 1, 2))
        color = _RISK_COLORS.get(zone.risk_level, (255, 255, 0))
        if overlay is None:
            overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
        x, y = polygon_px[0]
        cv2.putText(frame, zone.name, (int(x), max(int(y) - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    if overlay is not None:
        # Yarı saydam dolgu — bölge sınırı tek çizgiden daha okunur olur
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, dst=frame)
    return frame


def _placeholder_frame(message: str) -> bytes:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, message, (20, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)
    ok, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes() if ok else b""


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
    _draw_zones(annotated, rule_engine.get_zones(camera_id))
    ok, buffer = cv2.imencode(".jpg", annotated)
    if not ok:
        raise HTTPException(status_code=500, detail="JPEG encode başarısız")
    return Response(content=buffer.tobytes(), media_type="image/jpeg")


@router.get("/{camera_id}/stream")
async def detection_stream(camera_id: str, request: Request):
    """Kameranın canlı tespit görüntüsünü MJPEG olarak yayınlar (kutular,
    track ID, zone çizimleriyle). Tarayıcıda doğrudan açılabilir veya
    <img src="..."> ile gömülebilir: /api/detection/{camera_id}/stream"""

    async def frame_generator():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            if await request.is_disconnected():
                break

            result = detection_engine.get_latest_result(camera_id)
            if result is not None:
                annotated = annotate_frame(result)
                _draw_zones(annotated, rule_engine.get_zones(camera_id))
                ok, buffer = cv2.imencode(".jpg", annotated)
                payload = buffer.tobytes() if ok else _placeholder_frame("JPEG encode hatasi")
            else:
                payload = _placeholder_frame(f"'{camera_id}' icin frame bekleniyor...")

            yield boundary + payload + b"\r\n"
            await asyncio.sleep(1 / _STREAM_FPS)

    return StreamingResponse(
        frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/{camera_id}/view", response_class=HTMLResponse)
async def detection_view(camera_id: str):
    """Basit bir HTML sayfası döndürür — tarayıcıda kameranın canlı tespit
    akışını gösterir. Faz 6'daki React panelinden önce hızlı görsel doğrulama
    için kullanılır: /api/detection/{camera_id}/view"""
    # camera_id URL'den gelir — HTML'e gömmeden önce escape edilmeli
    # (reflected XSS önlemi); href için ayrıca URL-encode edilir.
    safe_id = html.escape(camera_id)
    safe_url_id = quote(camera_id, safe="")
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>{safe_id} — Canlı Tespit</title>
<style>
  body {{ background:#111; color:#eee; font-family:sans-serif; text-align:center; margin:0; padding:20px; }}
  img {{ max-width:95vw; border:2px solid #333; border-radius:8px; }}
  h2 {{ font-weight:400; }}
  a {{ color:#4fc3f7; }}
</style>
</head>
<body>
  <h2>{safe_id} — Canlı Tespit Akışı</h2>
  <img src="/api/detection/{safe_url_id}/stream" alt="canlı akış">
  <p><a href="/view">&larr; Tüm kameralar</a></p>
</body>
</html>"""
