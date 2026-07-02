"""Tracking Engine — Faz 3 (Gün 9–10)."""
from __future__ import annotations

from typing import Dict, List

import structlog

from app.config import settings
from app.detection.types import BBox
from app.tracking.bytetrack import ByteTracker
from app.tracking.types import TrackedObject

log = structlog.get_logger()


class TrackingEngine:
    """ByteTrack nesne takip motoru — her kamera için bağımsız bir
    ByteTracker örneği tutar (kamera başına ayrı state, roadmap §5.3)."""

    def __init__(self):
        self.trackers: Dict[str, ByteTracker] = {}  # camera_id → ByteTracker

    def update(self, camera_id: str, detections: List[BBox]) -> List[TrackedObject]:
        tracker = self.trackers.get(camera_id)
        if tracker is None:
            tracker = ByteTracker(
                high_thresh=settings.track_high_thresh,
                low_thresh=settings.track_low_thresh,
                new_thresh=settings.track_new_thresh,
                match_thresh=settings.track_match_thresh,
                max_age=settings.track_max_age,
            )
            self.trackers[camera_id] = tracker
            log.info("tracking.engine.tracker_created", camera_id=camera_id)
        return tracker.update(detections)

    def get_active_tracks(self, camera_id: str) -> List[TrackedObject]:
        """Yeni detection beklemeden mevcut track listesini döndürür (API/debug için)."""
        tracker = self.trackers.get(camera_id)
        if tracker is None:
            return []
        return tracker.active_tracks()


# ── Singleton ─────────────────────────────────────────────────────────────────
tracking_engine = TrackingEngine()
