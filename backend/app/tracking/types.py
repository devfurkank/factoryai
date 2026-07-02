"""Tracking veri tipleri."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class TrackState(str, Enum):
    TENTATIVE = "TENTATIVE"   # Henüz min_hits kadar eşleşmedi
    CONFIRMED = "CONFIRMED"   # Kararlı track — kural motoru bunu kullanır


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 — son bilinen konum
    confidence: float
    state: TrackState
    hits: int                 # Ardışık eşleşme sayısı
    time_since_update: int    # Kaç frame'dir eşleşmedi
    first_seen: float
    last_seen: float

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def to_dict(self) -> dict:
        x1, y1, x2, y2 = self.bbox
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "bbox": {"x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1)},
            "confidence": round(self.confidence, 3),
            "state": self.state.value,
            "hits": self.hits,
            "time_since_update": self.time_since_update,
        }
