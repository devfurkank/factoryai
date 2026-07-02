"""Tracking API — Kamera başına aktif track listesi (debug/doğrulama için)."""
from __future__ import annotations

from fastapi import APIRouter

from app.tracking.engine import tracking_engine

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.get("/{camera_id}/status")
async def tracking_status(camera_id: str):
    """Belirtilen kamerada şu an aktif olan (TENTATIVE + CONFIRMED) track'leri döndürür."""
    tracks = tracking_engine.get_active_tracks(camera_id)
    return {
        "camera_id": camera_id,
        "track_count": len(tracks),
        "tracks": [t.to_dict() for t in tracks],
    }
