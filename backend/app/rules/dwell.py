"""
Dwell Time (Bekleme Süresi) Kuralı — Roadmap §5.4 / §3.6.

MVP kapsamında "hareketsizlik tespiti" gerçek hareket miktarını ölçmek
yerine dwell time (bir bölgede sürekli kalma süresi) ile yaklaşıklanıyor
(bkz. Roadmap §3.6 MVP tablosu: "Hareketsizlik tespiti — Dwell time
kuralı"). Zone.rules JSON'ında `max_dwell_seconds` tanımlıysa, o bölgede
bu süreden fazla kalan her track için (allowed_classes'tan bağımsız —
dwell kuralı bölgedeki HERKESE uygulanır) bir kez INACTIVITY olayı üretir.
"""
from __future__ import annotations

import time
from typing import Dict, List, Set, Tuple

import shapely.geometry as geo
import structlog

from app.events.schemas import EventType
from app.rules.types import RuleViolation, ZoneData
from app.tracking.types import TrackedObject, TrackState

log = structlog.get_logger()


class DwellRuleEvaluator:
    # Kaybolmuş track / silinmiş zone anahtarları bu eşiğin üzerinde temizlenir.
    # Bölge bazlı temizlik (aşağıda) yalnızca hâlâ AKTİF zone'lar için çalışır;
    # zone silinir/pasifleşirse anahtarları ancak bu global süpürme toplar.
    _PRUNE_THRESHOLD = 1000

    def __init__(self):
        # (camera_id, zone_id, track_id) → bölgeye giriş zamanı
        self._entry_ts: Dict[Tuple[str, str, int], float] = {}
        # Zaten alarm üretilmiş (camera_id, zone_id, track_id) anahtarları
        self._alerted: Set[Tuple[str, str, int]] = set()

    def evaluate(
        self,
        camera_id: str,
        tracked_objects: List[TrackedObject],
        zones: List[ZoneData],
    ) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        now = time.time()

        dwell_zones = [
            z for z in zones
            if z.camera_id == camera_id and z.is_active and (z.rules or {}).get("max_dwell_seconds")
        ]

        for zone in dwell_zones:
            try:
                polygon = geo.Polygon(zone.polygon)
                if not polygon.is_valid or polygon.is_empty:
                    continue
            except Exception:
                continue

            max_seconds = float(zone.rules["max_dwell_seconds"])
            active_track_ids: Set[int] = set()

            for obj in tracked_objects:
                if obj.state != TrackState.CONFIRMED:
                    continue

                x1, y1, x2, y2 = obj.bbox
                foot_point = geo.Point((x1 + x2) / 2, y2)
                if not polygon.contains(foot_point):
                    continue

                active_track_ids.add(obj.track_id)
                key = (camera_id, zone.id, obj.track_id)
                entry_time = self._entry_ts.setdefault(key, now)
                dwell_seconds = now - entry_time

                if dwell_seconds >= max_seconds and key not in self._alerted:
                    self._alerted.add(key)
                    violations.append(RuleViolation(
                        camera_id=camera_id,
                        event_type=EventType.INACTIVITY,
                        track_ids=[obj.track_id],
                        detected_classes=[obj.class_name],
                        zone_id=zone.id,
                        risk_hint={"dwell_seconds": round(dwell_seconds, 1)},
                    ))

            # Bölgeyi terk eden track'lerin giriş kaydını temizle (yeniden
            # girerse dwell süresi sıfırdan başlasın)
            stale_keys = [
                k for k in self._entry_ts
                if k[0] == camera_id and k[1] == zone.id and k[2] not in active_track_ids
            ]
            for k in stale_keys:
                self._entry_ts.pop(k, None)
                self._alerted.discard(k)

        if len(self._entry_ts) >= self._PRUNE_THRESHOLD:
            current_ids = {o.track_id for o in tracked_objects}
            stale = [
                k for k in self._entry_ts
                if k[0] == camera_id and k[2] not in current_ids
            ]
            for k in stale:
                self._entry_ts.pop(k, None)
                self._alerted.discard(k)

        return violations
