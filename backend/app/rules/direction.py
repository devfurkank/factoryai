"""
Çizgi Geçiş / Yön Kuralı — Roadmap §5.4 & Gün 11-12 teknik görevleri.

Ayrı bir DB tablosu açmak yerine mevcut Zone modelinin `rules` JSON alanı
üzerinden tanımlanır:
    zone.rules = {
        "direction_line": [[x1, y1], [x2, y2]],
        "allowed_direction": "left_to_right" | "right_to_left",
    }
Bir track, önceki frame'de çizginin bir tarafındayken bu frame'de diğer
tarafına geçtiyse "çizgiyi geçti" sayılır. Geçiş yönü `allowed_direction`
ile uyuşmuyorsa DIRECTION_VIOLATION üretilir.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import structlog

from app.events.schemas import EventType
from app.rules.geometry import FrameSize, scale_points
from app.rules.types import RuleViolation, ZoneData
from app.tracking.types import TrackedObject, TrackState

log = structlog.get_logger()


def _line_side(lx1: float, ly1: float, lx2: float, ly2: float, px: float, py: float) -> float:
    """Noktanın çizginin hangi tarafında olduğunu işaretli alan (cross product) ile döner.
    > 0 ve < 0 çizginin iki farklı tarafını temsil eder."""
    return (lx2 - lx1) * (py - ly1) - (ly2 - ly1) * (px - lx1)


class DirectionRuleEvaluator:
    # Kaybolmuş track anahtarları bu eşiğin üzerinde temizlenir (bellek sızıntısı
    # önlemi — track ID'ler monoton artar, bkz. ZoneRuleEvaluator._prune)
    _PRUNE_THRESHOLD = 1000

    def __init__(self):
        # (camera_id, zone_id, track_id) → son bilinen taraf (işaret)
        self._last_side: Dict[Tuple[str, str, int], float] = {}

    def evaluate(
        self,
        camera_id: str,
        tracked_objects: List[TrackedObject],
        zones: List[ZoneData],
        frame_size: Optional[FrameSize] = None,
    ) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        direction_zones = [
            z for z in zones
            if z.camera_id == camera_id and z.is_active and (z.rules or {}).get("direction_line")
        ]

        for zone in direction_zones:
            line = zone.rules.get("direction_line")
            allowed_direction = zone.rules.get("allowed_direction", "any")
            if allowed_direction == "any" or not line or len(line) != 2:
                continue

            (lx1, ly1), (lx2, ly2) = scale_points(line, frame_size)

            for obj in tracked_objects:
                if obj.state != TrackState.CONFIRMED:
                    continue

                cx, cy = obj.center
                side = _line_side(lx1, ly1, lx2, ly2, cx, cy)
                key = (camera_id, zone.id, obj.track_id)
                prev_side = self._last_side.get(key)

                if prev_side is not None and side != 0 and _sign(prev_side) != _sign(side):
                    crossing_direction = "left_to_right" if side > 0 else "right_to_left"
                    if crossing_direction != allowed_direction:
                        violations.append(RuleViolation(
                            camera_id=camera_id,
                            event_type=EventType.DIRECTION_VIOLATION,
                            track_ids=[obj.track_id],
                            detected_classes=[obj.class_name],
                            zone_id=zone.id,
                            risk_hint={"direction": crossing_direction},
                        ))

                self._last_side[key] = side

        if len(self._last_side) >= self._PRUNE_THRESHOLD:
            current_ids = {o.track_id for o in tracked_objects}
            stale = [
                k for k in self._last_side
                if k[0] == camera_id and k[2] not in current_ids
            ]
            for k in stale:
                del self._last_side[k]

        return violations


def _sign(value: float) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)
