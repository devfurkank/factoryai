"""Rule Engine — Faz 3 (Gün 11–12)."""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

import structlog

from app.config import settings
from app.rules.distance import DistanceRuleEvaluator
from app.rules.direction import DirectionRuleEvaluator
from app.rules.dwell import DwellRuleEvaluator
from app.rules.types import RuleViolation, ZoneData
from app.rules.zone import ZoneRuleEvaluator
from app.tracking.types import TrackedObject

log = structlog.get_logger()


class RuleEngine:
    """Polygon zone, dwell time, mesafe ve yön kurallarını değerlendirir.

    Zone tanımları DB'den periyodik olarak (bkz. main.py::_zones_refresher)
    `set_zones` ile önbelleğe alınır; `evaluate` her çağrıda DB'ye gitmez."""

    def __init__(self):
        self._zones_by_camera: Dict[str, List[ZoneData]] = {}
        self._zone_eval = ZoneRuleEvaluator()
        self._dwell_eval = DwellRuleEvaluator()
        self._distance_eval = DistanceRuleEvaluator()
        self._direction_eval = DirectionRuleEvaluator()
        self._recent: Dict[str, deque] = {}  # camera_id → deque[RuleViolation] (debug/API)

    def set_zones(self, zones_by_camera: Dict[str, List[ZoneData]]):
        self._zones_by_camera = zones_by_camera

    def evaluate(
        self,
        camera_id: str,
        tracked_objects: List[TrackedObject],
        zones: Optional[List[ZoneData]] = None,
    ) -> List[RuleViolation]:
        cam_zones = zones if zones is not None else self._zones_by_camera.get(camera_id, [])

        violations: List[RuleViolation] = []
        violations += self._zone_eval.evaluate(camera_id, tracked_objects, cam_zones)
        violations += self._dwell_eval.evaluate(camera_id, tracked_objects, cam_zones)
        violations += self._distance_eval.evaluate(
            camera_id, tracked_objects, settings.distance_alert_pixels
        )
        violations += self._direction_eval.evaluate(camera_id, tracked_objects, cam_zones)

        if violations:
            buf = self._recent.setdefault(camera_id, deque(maxlen=50))
            buf.extend(violations)
            for v in violations:
                log.warning(
                    "rule.violation",
                    camera_id=camera_id,
                    event_type=v.event_type.value,
                    track_ids=v.track_ids,
                    zone_id=v.zone_id,
                    **v.risk_hint,
                )

        return violations

    def get_recent_violations(self, camera_id: str) -> List[RuleViolation]:
        return list(self._recent.get(camera_id, []))

    def get_zones(self, camera_id: str) -> List[ZoneData]:
        """Önbellekteki zone listesini döndürür (debug/görselleştirme için)."""
        return self._zones_by_camera.get(camera_id, [])


# ── Singleton ─────────────────────────────────────────────────────────────────
rule_engine = RuleEngine()
