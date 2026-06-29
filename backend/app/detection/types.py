"""
Detection veri tipleri — tüm tespit modülleri bu tipleri kullanır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np


class FallState(str, Enum):
    NORMAL = "NORMAL"
    CANDIDATE = "CANDIDATE"    # Açı eşiği aşıldı, henüz onaylanmadı
    CONFIRMED = "CONFIRMED"    # 3+ ardışık frame'de açı eşiği aşıldı
    SUSTAINED = "SUSTAINED"    # Onaylı düşme + 30 sn hareketsizlik


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str
    track_id: Optional[int] = None

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class PoseResult:
    bbox: BBox
    keypoints: List[List[float]]  # [[x, y, conf], ...] — 17 COCO keypoint
    body_angle: float              # Gövde dikeyden sapma açısı (derece)
    fall_state: FallState = FallState.NORMAL
    track_id: Optional[int] = None


@dataclass
class DetectionResult:
    camera_id: str
    timestamp: float
    frame: np.ndarray                                         # Ham frame
    general: List[BBox] = field(default_factory=list)        # person, vehicle
    ppe: List[BBox] = field(default_factory=list)             # hardhat, no_hardhat
    fire_smoke: List[BBox] = field(default_factory=list)      # fire, smoke (onaylı)
    poses: List[PoseResult] = field(default_factory=list)     # poz + düşme durumu
    annotated_frame: Optional[np.ndarray] = None              # Debug annotation

    @property
    def has_fire(self) -> bool:
        return any("fire" in b.class_name.lower() or "yangın" in b.class_name.lower()
                   for b in self.fire_smoke)

    @property
    def has_smoke(self) -> bool:
        return any("smoke" in b.class_name.lower() or "duman" in b.class_name.lower()
                   for b in self.fire_smoke)

    @property
    def has_fall(self) -> bool:
        return any(p.fall_state in (FallState.CONFIRMED, FallState.SUSTAINED)
                   for p in self.poses)

    @property
    def has_ppe_violation(self) -> bool:
        return any("no" in b.class_name.lower() for b in self.ppe)

    @property
    def person_count(self) -> int:
        return sum(1 for b in self.general if b.class_name == "person")

    def summary(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "timestamp": self.timestamp,
            "persons": self.person_count,
            "vehicles": sum(1 for b in self.general if b.class_name == "vehicle"),
            "ppe_violations": sum(1 for b in self.ppe if "no" in b.class_name.lower()),
            "fire": self.has_fire,
            "smoke": self.has_smoke,
            "fall": self.has_fall,
        }
