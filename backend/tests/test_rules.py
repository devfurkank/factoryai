"""Rule Engine modülü testleri — Faz 3 (zone, dwell, distance, direction)."""
import time

from app.events.schemas import EventType
from app.rules.direction import DirectionRuleEvaluator
from app.rules.distance import DistanceRuleEvaluator
from app.rules.dwell import DwellRuleEvaluator
from app.rules.engine import RuleEngine
from app.rules.geometry import is_normalized, scale_points
from app.rules.types import ZoneData
from app.rules.zone import ZoneRuleEvaluator
from app.tracking.types import TrackedObject, TrackState


def _obj(track_id, cx, cy, class_name="person", state=TrackState.CONFIRMED, half=10):
    return TrackedObject(
        track_id=track_id,
        class_name=class_name,
        bbox=(cx - half, cy - half, cx + half, cy + half),
        confidence=0.9,
        state=state,
        hits=3,
        time_since_update=0,
        first_seen=0.0,
        last_seen=0.0,
    )


# ── Zone Rule ────────────────────────────────────────────────────────────────
class TestZoneRule:
    def _zone(self, allowed=None):
        return ZoneData(
            id="z1", camera_id="cam_01", name="Yasak Bölge", zone_type="forbidden",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="high",
            allowed_classes=allowed or [], rules={},
        )

    def test_entry_triggers_violation(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone()
        obj = _obj(1, 50, 50)
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert len(violations) == 1
        assert violations[0].event_type == EventType.FORBIDDEN_ZONE_ENTRY
        assert violations[0].track_ids == [1]
        assert violations[0].zone_id == "z1"

    def test_staying_inside_does_not_retrigger(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone()
        obj = _obj(1, 50, 50)
        evaluator.evaluate("cam_01", [obj], [zone])
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []

    def test_outside_zone_no_violation(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone()
        obj = _obj(1, 500, 500)
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []

    def test_allowed_class_skipped(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone(allowed=["vehicle"])
        obj = _obj(1, 50, 50, class_name="vehicle")
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []

    def test_tentative_track_ignored(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone()
        obj = _obj(1, 50, 50, state=TrackState.TENTATIVE)
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []

    def test_reentry_after_exit_triggers_again(self):
        evaluator = ZoneRuleEvaluator()
        zone = self._zone()
        obj_in = _obj(1, 50, 50)
        obj_out = _obj(1, 500, 500)
        assert len(evaluator.evaluate("cam_01", [obj_in], [zone])) == 1
        evaluator.evaluate("cam_01", [obj_out], [zone])
        assert len(evaluator.evaluate("cam_01", [obj_in], [zone])) == 1

    def test_invalid_polygon_ignored(self):
        evaluator = ZoneRuleEvaluator()
        zone = ZoneData(
            id="z2", camera_id="cam_01", name="Bozuk", zone_type="forbidden",
            polygon=[[0, 0], [10, 0]],  # 3 noktadan az — geçersiz poligon
            risk_level="high", allowed_classes=[], rules={},
        )
        obj = _obj(1, 5, 0)
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []


# ── Dwell Rule ───────────────────────────────────────────────────────────────
class TestDwellRule:
    def _zone(self, max_dwell=10.0):
        return ZoneData(
            id="z1", camera_id="cam_01", name="Bekleme Alanı", zone_type="dwell",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="medium",
            allowed_classes=[], rules={"max_dwell_seconds": max_dwell},
        )

    def test_no_alert_before_threshold(self, monkeypatch):
        evaluator = DwellRuleEvaluator()
        t0 = 1000.0
        monkeypatch.setattr(time, "time", lambda: t0)
        zone = self._zone(max_dwell=10.0)
        obj = _obj(1, 50, 50)
        assert evaluator.evaluate("cam_01", [obj], [zone]) == []

        monkeypatch.setattr(time, "time", lambda: t0 + 5.0)
        assert evaluator.evaluate("cam_01", [obj], [zone]) == []

    def test_alert_after_threshold_once(self, monkeypatch):
        evaluator = DwellRuleEvaluator()
        t0 = 1000.0
        monkeypatch.setattr(time, "time", lambda: t0)
        zone = self._zone(max_dwell=10.0)
        obj = _obj(1, 50, 50)
        evaluator.evaluate("cam_01", [obj], [zone])

        monkeypatch.setattr(time, "time", lambda: t0 + 11.0)
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert len(violations) == 1
        assert violations[0].event_type == EventType.INACTIVITY
        assert violations[0].risk_hint["dwell_seconds"] >= 10.0

        # Tekrar çağrıldığında (aynı track, hâlâ içeride) tekrar üretilmemeli
        monkeypatch.setattr(time, "time", lambda: t0 + 12.0)
        assert evaluator.evaluate("cam_01", [obj], [zone]) == []

    def test_leaving_zone_resets_timer(self, monkeypatch):
        evaluator = DwellRuleEvaluator()
        t0 = 1000.0
        monkeypatch.setattr(time, "time", lambda: t0)
        zone = self._zone(max_dwell=10.0)
        obj_inside = _obj(1, 50, 50)
        obj_outside = _obj(1, 500, 500)

        evaluator.evaluate("cam_01", [obj_inside], [zone])

        monkeypatch.setattr(time, "time", lambda: t0 + 3.0)
        evaluator.evaluate("cam_01", [obj_outside], [zone])  # bölgeden çıktı → timer temizlenir

        monkeypatch.setattr(time, "time", lambda: t0 + 3.0)
        evaluator.evaluate("cam_01", [obj_inside], [zone])  # tekrar girdi → süre sıfırdan başlar

        monkeypatch.setattr(time, "time", lambda: t0 + 12.0)  # yeniden giriş sonrası sadece 9 sn
        assert evaluator.evaluate("cam_01", [obj_inside], [zone]) == []


# ── Distance Rule ────────────────────────────────────────────────────────────
class TestDistanceRule:
    def test_close_pair_triggers_once(self):
        evaluator = DistanceRuleEvaluator()
        person = _obj(1, 100, 100, class_name="person")
        vehicle = _obj(2, 120, 100, class_name="vehicle")  # 20px mesafe
        v1 = evaluator.evaluate("cam_01", [person, vehicle], min_distance_px=50.0)
        assert len(v1) == 1
        assert v1[0].event_type == EventType.FORKLIFT_PROXIMITY
        assert set(v1[0].track_ids) == {1, 2}

        v2 = evaluator.evaluate("cam_01", [person, vehicle], min_distance_px=50.0)
        assert v2 == []  # zaten aktif ihlal, spam üretilmez

    def test_far_pair_no_violation(self):
        evaluator = DistanceRuleEvaluator()
        person = _obj(1, 0, 0, class_name="person")
        vehicle = _obj(2, 1000, 1000, class_name="vehicle")
        violations = evaluator.evaluate("cam_01", [person, vehicle], min_distance_px=50.0)
        assert violations == []

    def test_retrigger_after_separation(self):
        evaluator = DistanceRuleEvaluator()
        person = _obj(1, 100, 100, class_name="person")
        close_vehicle = _obj(2, 120, 100, class_name="vehicle")
        far_vehicle = _obj(2, 1000, 1000, class_name="vehicle")

        evaluator.evaluate("cam_01", [person, close_vehicle], min_distance_px=50.0)
        evaluator.evaluate("cam_01", [person, far_vehicle], min_distance_px=50.0)
        v = evaluator.evaluate("cam_01", [person, close_vehicle], min_distance_px=50.0)
        assert len(v) == 1


# ── Direction Rule ───────────────────────────────────────────────────────────
class TestDirectionRule:
    def _zone(self, allowed_direction="left_to_right"):
        return ZoneData(
            id="z1", camera_id="cam_01", name="Giriş Çizgisi", zone_type="direction",
            polygon=[], risk_level="low", allowed_classes=[],
            rules={"direction_line": [[100, 0], [100, 200]], "allowed_direction": allowed_direction},
        )

    def test_crossing_disallowed_direction_triggers(self):
        # Bu dikey çizgi ve x: 50→150 hareketi için _line_side işareti
        # pozitiften negatife döner ve kod bunu "right_to_left" etiketler.
        evaluator = DirectionRuleEvaluator()
        zone = self._zone(allowed_direction="left_to_right")
        obj_left = _obj(1, 50, 100)
        obj_right = _obj(1, 150, 100)
        evaluator.evaluate("cam_01", [obj_left], [zone])
        violations = evaluator.evaluate("cam_01", [obj_right], [zone])
        assert len(violations) == 1
        assert violations[0].event_type == EventType.DIRECTION_VIOLATION
        assert violations[0].risk_hint["direction"] == "right_to_left"

    def test_crossing_allowed_direction_no_violation(self):
        evaluator = DirectionRuleEvaluator()
        zone = self._zone(allowed_direction="right_to_left")
        obj_left = _obj(1, 50, 100)
        obj_right = _obj(1, 150, 100)
        evaluator.evaluate("cam_01", [obj_left], [zone])
        violations = evaluator.evaluate("cam_01", [obj_right], [zone])
        assert violations == []

    def test_no_crossing_no_violation(self):
        evaluator = DirectionRuleEvaluator()
        zone = self._zone(allowed_direction="left_to_right")
        obj = _obj(1, 50, 100)
        evaluator.evaluate("cam_01", [obj], [zone])
        violations = evaluator.evaluate("cam_01", [obj], [zone])
        assert violations == []

    def test_any_direction_disables_rule(self):
        evaluator = DirectionRuleEvaluator()
        zone = self._zone(allowed_direction="any")
        obj_left = _obj(1, 50, 100)
        obj_right = _obj(1, 150, 100)
        evaluator.evaluate("cam_01", [obj_left], [zone])
        violations = evaluator.evaluate("cam_01", [obj_right], [zone])
        assert violations == []


# ── RuleEngine orkestrasyon ────────────────────────────────────────────────────
class TestRuleEngineOrchestration:
    def test_evaluate_uses_cached_zones_and_records_recent(self):
        engine = RuleEngine()
        zone = ZoneData(
            id="z1", camera_id="cam_01", name="Yasak Bölge", zone_type="forbidden",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="high",
            allowed_classes=[], rules={},
        )
        engine.set_zones({"cam_01": [zone]})
        obj = _obj(1, 50, 50)

        violations = engine.evaluate("cam_01", [obj])
        assert len(violations) == 1
        assert engine.get_recent_violations("cam_01") == violations

    def test_evaluate_explicit_zones_overrides_cache(self):
        engine = RuleEngine()
        engine.set_zones({"cam_01": []})
        zone = ZoneData(
            id="z1", camera_id="cam_01", name="Yasak Bölge", zone_type="forbidden",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="high",
            allowed_classes=[], rules={},
        )
        obj = _obj(1, 50, 50)
        violations = engine.evaluate("cam_01", [obj], zones=[zone])
        assert len(violations) == 1

    def test_no_zones_no_violations(self):
        engine = RuleEngine()
        obj = _obj(1, 50, 50)
        assert engine.evaluate("cam_01", [obj]) == []


# ── State Pruning (bellek sızıntısı önlemi — code review düzeltmesi) ─────────
class TestStatePruning:
    """Track ID'ler monoton arttığı için evaluator state sözlükleri temizlik
    yapılmazsa 7/24 sistemde sınırsız büyür. Eşik aşıldığında kaybolmuş
    track'lerin anahtarları atılmalı."""

    def _zone(self, zone_id="z1", rules=None):
        return ZoneData(
            id=zone_id, camera_id="cam_01", name="Bölge", zone_type="forbidden",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="high",
            allowed_classes=[], rules=rules or {},
        )

    def test_zone_state_pruned_for_lost_tracks(self, monkeypatch):
        monkeypatch.setattr(ZoneRuleEvaluator, "_PRUNE_THRESHOLD", 3)
        ev = ZoneRuleEvaluator()
        zone = self._zone()
        # 4 track içeride → 4 state anahtarı
        ev.evaluate("cam_01", [_obj(i, 50, 50) for i in range(1, 5)], [zone])
        assert len(ev._inside_state) == 4
        # Sadece track 99 kaldı → eskiler temizlenmeli
        ev.evaluate("cam_01", [_obj(99, 50, 50)], [zone])
        assert set(k[2] for k in ev._inside_state) == {99}

    def test_zone_state_not_pruned_below_threshold(self):
        ev = ZoneRuleEvaluator()  # varsayılan eşik 1000
        zone = self._zone()
        ev.evaluate("cam_01", [_obj(1, 50, 50)], [zone])
        ev.evaluate("cam_01", [_obj(2, 50, 50)], [zone])
        # Eşik altında track 1'in anahtarı korunur (flicker toleransı)
        assert (("cam_01", "z1", 1) in ev._inside_state)

    def test_direction_state_pruned(self, monkeypatch):
        monkeypatch.setattr(DirectionRuleEvaluator, "_PRUNE_THRESHOLD", 3)
        ev = DirectionRuleEvaluator()
        zone = self._zone(rules={
            "direction_line": [[50, 0], [50, 100]],
            "allowed_direction": "left_to_right",
        })
        ev.evaluate("cam_01", [_obj(i, 20, 50) for i in range(1, 5)], [zone])
        assert len(ev._last_side) == 4
        ev.evaluate("cam_01", [_obj(99, 20, 50)], [zone])
        assert set(k[2] for k in ev._last_side) == {99}

    def test_dwell_state_pruned_even_when_zone_deleted(self, monkeypatch):
        monkeypatch.setattr(DwellRuleEvaluator, "_PRUNE_THRESHOLD", 3)
        ev = DwellRuleEvaluator()
        zone = self._zone(rules={"max_dwell_seconds": 999})
        ev.evaluate("cam_01", [_obj(i, 50, 50) for i in range(1, 5)], [zone])
        assert len(ev._entry_ts) == 4
        # Zone silindi (listede yok) — bölge bazlı temizlik çalışamaz,
        # global süpürme eski anahtarları yine de toplamalı
        ev.evaluate("cam_01", [_obj(99, 50, 50)], [])
        assert all(k[2] == 99 or k not in ev._entry_ts for k in list(ev._entry_ts))
        assert not any(k[2] in (1, 2, 3, 4) for k in ev._entry_ts)


# ── Normalize (0-1) koordinat desteği — web paneli çizim aracı ────────────────
class TestGeometryHelpers:
    def test_is_normalized_true_for_unit_range(self):
        assert is_normalized([[0.1, 0.2], [0.9, 0.4], [0.5, 1.0]])

    def test_is_normalized_false_for_pixels(self):
        assert not is_normalized([[0, 0], [100, 0], [100, 100]])

    def test_is_normalized_false_for_empty_or_malformed(self):
        assert not is_normalized([])
        assert not is_normalized([[0.5], [0.2, 0.3]])
        assert not is_normalized([["a", "b"]])

    def test_scale_points_scales_normalized_to_frame(self):
        # frame_size = (height, width) — numpy shape[:2] sırası
        pts = scale_points([[0.5, 0.25], [1.0, 1.0]], (480, 640))
        assert pts == [[320.0, 120.0], [640.0, 480.0]]

    def test_scale_points_leaves_pixels_untouched(self):
        pts = scale_points([[10, 20], [300, 400], [50, 60]], (480, 640))
        assert pts == [[10, 20], [300, 400], [50, 60]]

    def test_scale_points_without_frame_size_returns_as_is(self):
        pts = scale_points([[0.5, 0.5], [0.9, 0.1], [0.2, 0.8]], None)
        assert pts == [[0.5, 0.5], [0.9, 0.1], [0.2, 0.8]]


class TestNormalizedZoneRule:
    # 640x480 frame'de x:64-320 / y:48-240 piksel bölgesine denk gelir
    def _normalized_zone(self):
        return ZoneData(
            id="zn1", camera_id="cam_01", name="Normalize Bölge",
            zone_type="forbidden",
            polygon=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            risk_level="high", allowed_classes=[], rules={},
        )

    def test_entry_inside_normalized_zone_triggers(self):
        evaluator = ZoneRuleEvaluator()
        obj = _obj(1, 150, 100)  # ayak noktası (150, 110) → bölge içinde
        violations = evaluator.evaluate(
            "cam_01", [obj], [self._normalized_zone()], frame_size=(480, 640)
        )
        assert len(violations) == 1
        assert violations[0].event_type == EventType.FORBIDDEN_ZONE_ENTRY
        assert violations[0].zone_id == "zn1"

    def test_outside_normalized_zone_does_not_trigger(self):
        evaluator = ZoneRuleEvaluator()
        obj = _obj(1, 500, 400)  # ayak noktası (500, 410) → bölge dışında
        violations = evaluator.evaluate(
            "cam_01", [obj], [self._normalized_zone()], frame_size=(480, 640)
        )
        assert violations == []

    def test_normalized_zone_without_frame_size_is_inert(self):
        # frame_size bilinmiyorsa 1x1'lik poligon hiçbir piksel bbox'ını içeremez
        evaluator = ZoneRuleEvaluator()
        obj = _obj(1, 150, 100)
        violations = evaluator.evaluate("cam_01", [obj], [self._normalized_zone()])
        assert violations == []

    def test_pixel_zone_behavior_unchanged_with_frame_size(self):
        evaluator = ZoneRuleEvaluator()
        zone = ZoneData(
            id="zp1", camera_id="cam_01", name="Piksel Bölge", zone_type="forbidden",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]], risk_level="high",
            allowed_classes=[], rules={},
        )
        obj = _obj(1, 50, 50)
        violations = evaluator.evaluate("cam_01", [obj], [zone], frame_size=(480, 640))
        assert len(violations) == 1

    def test_rule_engine_passes_frame_size_through(self):
        engine = RuleEngine()
        engine.set_zones({"cam_01": [self._normalized_zone()]})
        obj = _obj(1, 150, 100)
        violations = engine.evaluate("cam_01", [obj], frame_size=(480, 640))
        assert len(violations) == 1
        assert violations[0].event_type == EventType.FORBIDDEN_ZONE_ENTRY

    def test_dwell_with_normalized_polygon(self, monkeypatch):
        evaluator = DwellRuleEvaluator()
        zone = ZoneData(
            id="zn2", camera_id="cam_01", name="Normalize Bekleme", zone_type="dwell",
            polygon=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            risk_level="medium", allowed_classes=[],
            rules={"max_dwell_seconds": 10.0},
        )
        obj = _obj(1, 150, 100)
        t0 = 1000.0
        monkeypatch.setattr(time, "time", lambda: t0)
        assert evaluator.evaluate("cam_01", [obj], [zone], frame_size=(480, 640)) == []
        monkeypatch.setattr(time, "time", lambda: t0 + 11.0)
        violations = evaluator.evaluate("cam_01", [obj], [zone], frame_size=(480, 640))
        assert len(violations) == 1
        assert violations[0].event_type == EventType.INACTIVITY
