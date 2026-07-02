"""
Mesafe (Forklift-İnsan Yakınlık) Kuralı — Roadmap §5.4.

NOT: COCO tabanlı genel modelde ayrı bir 'forklift' sınıfı yok; tüm araçlar
(car/motorcycle/bus/truck) 'vehicle' etiketi altında birleştiriliyor (bkz.
detection/yolo.py::COCO_FACTORY_MAP). Bu yüzden mesafe kuralı forklift
yerine 'vehicle' sınıfını vekil olarak kullanıyor — özel forklift modeli
eğitilene kadar bu pragmatik yaklaşım yeterli (proje genelinde
fire_detection.pt için de benzer bir yaklaşım benimsenmişti).
"""
from __future__ import annotations

import math
from typing import List, Set, Tuple

import structlog

from app.events.schemas import EventType
from app.rules.types import RuleViolation
from app.tracking.types import TrackedObject, TrackState

log = structlog.get_logger()


def _center_distance(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax = (a[0] + a[2]) / 2
    ay = (a[1] + a[3]) / 2
    bx = (b[0] + b[2]) / 2
    by = (b[1] + b[3]) / 2
    return math.hypot(ax - bx, ay - by)


class DistanceRuleEvaluator:
    def __init__(self):
        # Aktif (camera_id, person_track_id, vehicle_track_id) ihlal çiftleri
        self._alerted: Set[Tuple[str, int, int]] = set()

    def evaluate(
        self,
        camera_id: str,
        tracked_objects: List[TrackedObject],
        min_distance_px: float,
    ) -> List[RuleViolation]:
        persons = [o for o in tracked_objects if o.state == TrackState.CONFIRMED and o.class_name == "person"]
        vehicles = [o for o in tracked_objects if o.state == TrackState.CONFIRMED and o.class_name == "vehicle"]

        violations: List[RuleViolation] = []
        active_pairs: Set[Tuple[str, int, int]] = set()

        for p in persons:
            for v in vehicles:
                distance = _center_distance(p.bbox, v.bbox)
                if distance > min_distance_px:
                    continue
                pair_key = (camera_id, p.track_id, v.track_id)
                active_pairs.add(pair_key)
                if pair_key not in self._alerted:
                    self._alerted.add(pair_key)
                    violations.append(RuleViolation(
                        camera_id=camera_id,
                        event_type=EventType.FORKLIFT_PROXIMITY,
                        track_ids=[p.track_id, v.track_id],
                        detected_classes=["person", "vehicle"],
                        risk_hint={"distance_px": round(distance, 1)},
                    ))

        # Bu kamerada artık geçerli olmayan çiftleri temizle (tekrar
        # yaklaşırlarsa yeni bir alarm üretilebilsin)
        self._alerted = {
            k for k in self._alerted if k[0] != camera_id or k in active_pairs
        }
        return violations
