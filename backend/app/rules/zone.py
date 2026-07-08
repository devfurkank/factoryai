"""
Poligon Bölge (Zone) Kuralı — Roadmap §5.4.

İzin verilmeyen sınıftaki bir nesne bölgeye YENİ girdiğinde bir kez alarm
üretir (giriş kenarı tespiti). Nesne bölge içinde kaldığı sürece tekrar
alarm üretmez — sürekli spam yerine "entry edge" mantığı kullanılır.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import shapely.geometry as geo
import structlog

from app.events.schemas import EventType
from app.rules.geometry import FrameSize, scale_points
from app.rules.types import RuleViolation, ZoneData
from app.tracking.types import TrackedObject, TrackState

log = structlog.get_logger()


class ZoneRuleEvaluator:
    # State sözlüğü bu boyutu aşınca kaybolmuş track'lerin anahtarları temizlenir
    # (track ID'ler monoton arttığı için temizlik yapılmazsa 7/24 çalışan
    # sistemde sınırsız büyür — EventEngine._prune_dedup_cache ile aynı önlem)
    _PRUNE_THRESHOLD = 1000

    def __init__(self):
        # (camera_id, zone_id, track_id) → son bilinen "içeride mi" durumu
        self._inside_state: Dict[Tuple[str, str, int], bool] = {}

    def evaluate(
        self,
        camera_id: str,
        tracked_objects: List[TrackedObject],
        zones: List[ZoneData],
        frame_size: Optional[FrameSize] = None,
    ) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        cam_zones = [z for z in zones if z.camera_id == camera_id and z.is_active]

        for zone in cam_zones:
            polygon = self._build_polygon(zone, frame_size)
            if polygon is None:
                continue

            allowed = {c.lower() for c in (zone.allowed_classes or [])}

            for obj in tracked_objects:
                if obj.state != TrackState.CONFIRMED:
                    continue

                key = (camera_id, zone.id, obj.track_id)

                if obj.class_name.lower() in allowed:
                    self._inside_state.pop(key, None)
                    continue

                x1, y1, x2, y2 = obj.bbox
                foot_point = geo.Point((x1 + x2) / 2, y2)  # ayak izi (alt-orta)
                inside = polygon.contains(foot_point)
                was_inside = self._inside_state.get(key, False)

                if inside and not was_inside:
                    violations.append(RuleViolation(
                        camera_id=camera_id,
                        event_type=EventType.FORBIDDEN_ZONE_ENTRY,
                        track_ids=[obj.track_id],
                        detected_classes=[obj.class_name],
                        zone_id=zone.id,
                        risk_hint={"risk_level": zone.risk_level},
                    ))

                self._inside_state[key] = inside

        self._prune(camera_id, tracked_objects)
        return violations

    def _prune(self, camera_id: str, tracked_objects: List[TrackedObject]):
        """Bu kamerada artık görünmeyen track'lerin state anahtarlarını atar.
        Eşik altında hiç çalışmaz — track'in tek frame'lik kaybolmalarında
        (flicker) yeniden-giriş alarmı üretme riskini pratikte sıfırlar."""
        if len(self._inside_state) < self._PRUNE_THRESHOLD:
            return
        current_ids = {o.track_id for o in tracked_objects}
        stale = [
            k for k in self._inside_state
            if k[0] == camera_id and k[2] not in current_ids
        ]
        for k in stale:
            del self._inside_state[k]

    @staticmethod
    def _build_polygon(zone: ZoneData, frame_size: Optional[FrameSize] = None):
        try:
            # Normalize (0-1) kaydedilen poligonlar frame boyutuna ölçeklenir;
            # piksel poligonlar aynen kullanılır (bkz. rules/geometry.py)
            polygon = geo.Polygon(scale_points(zone.polygon, frame_size))
        except Exception:
            log.warning("rules.zone.invalid_polygon", zone_id=zone.id)
            return None
        if not polygon.is_valid or polygon.is_empty:
            log.warning("rules.zone.degenerate_polygon", zone_id=zone.id)
            return None
        return polygon
