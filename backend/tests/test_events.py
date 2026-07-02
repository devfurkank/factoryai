"""Event Engine modülü testleri — Faz 4 (scoring, lifecycle, dedup, thumbnail)."""
import cv2
import numpy as np
import pytest

from app.detection.types import BBox, DetectionResult, FallState, PoseResult
from app.events.engine import EventEngine
from app.events.lifecycle import (
    InvalidTransition,
    can_transition,
    is_terminal,
    validate_transition,
)
from app.events.schemas import EventCreate, EventStatus, EventType, Severity
from app.events.scoring import compute_risk_score, severity_for_score
from app.events.thumbnails import render_thumbnail, save_thumbnail
from app.rules.types import RuleViolation


def _violation(
    event_type=EventType.FORBIDDEN_ZONE_ENTRY,
    camera_id="cam_01",
    track_ids=None,
    zone_id="z1",
    risk_hint=None,
    timestamp=1000.0,
):
    return RuleViolation(
        camera_id=camera_id,
        event_type=event_type,
        track_ids=track_ids if track_ids is not None else [1],
        detected_classes=["person"],
        zone_id=zone_id,
        risk_hint=risk_hint or {},
        timestamp=timestamp,
    )


def _bbox(class_name="person", conf=0.9, track_id=None):
    return BBox(x1=10, y1=10, x2=60, y2=100, confidence=conf,
                class_id=0, class_name=class_name, track_id=track_id)


def _result(camera_id="cam_01", timestamp=1000.0, **kwargs):
    return DetectionResult(
        camera_id=camera_id,
        timestamp=timestamp,
        frame=np.zeros((120, 160, 3), dtype=np.uint8),
        **kwargs,
    )


# ── Risk Puanlama (Roadmap §5.5 matrisi) ─────────────────────────────────────
class TestRiskScoring:
    def test_forbidden_zone_base_score(self):
        assert compute_risk_score(EventType.FORBIDDEN_ZONE_ENTRY, {"risk_level": "medium"}) == 70

    def test_forbidden_zone_high_risk_multiplier(self):
        # 70 × 1.5 = 105 → 100'e kırpılır
        assert compute_risk_score(EventType.FORBIDDEN_ZONE_ENTRY, {"risk_level": "high"}) == 100

    def test_forbidden_zone_low_risk(self):
        assert compute_risk_score(EventType.FORBIDDEN_ZONE_ENTRY, {"risk_level": "low"}) == 56

    def test_ppe_single_person(self):
        assert compute_risk_score(EventType.PPE_VIOLATION, {"person_count": 1}) == 60

    def test_ppe_multiple_persons_multiplier(self):
        assert compute_risk_score(EventType.PPE_VIOLATION, {"person_count": 3}) == 72

    def test_fall_base(self):
        assert compute_risk_score(EventType.FALL, {}) == 95

    def test_fall_sustained_clamped_to_100(self):
        assert compute_risk_score(EventType.FALL, {"sustained": True}) == 100

    def test_fire_always_maximum(self):
        assert compute_risk_score(EventType.FIRE, {}) == 100
        assert compute_risk_score(EventType.FIRE, {"confidence": 0.4}) == 100

    def test_smoke_low_confidence_base(self):
        assert compute_risk_score(EventType.SMOKE, {"confidence": 0.5}) == 80

    def test_smoke_high_confidence_multiplier(self):
        # 80 × 1.4 = 112 → 100'e kırpılır
        assert compute_risk_score(EventType.SMOKE, {"confidence": 0.8}) == 100

    def test_inactivity_location_criticality(self):
        assert compute_risk_score(EventType.INACTIVITY, {"risk_level": "medium"}) == 75
        assert compute_risk_score(EventType.INACTIVITY, {"risk_level": "high"}) == 90

    def test_proximity_far_base(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "distance_alert_pixels", 150.0)
        # Eşik 150px → "çok yakın" sınırı 75px; 100px sadece baz puan alır
        assert compute_risk_score(EventType.FORKLIFT_PROXIMITY, {"distance_px": 100.0}) == 65

    def test_proximity_very_close_doubles(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "distance_alert_pixels", 150.0)
        # 65 × 2.0 = 130 → 100'e kırpılır
        assert compute_risk_score(EventType.FORKLIFT_PROXIMITY, {"distance_px": 50.0}) == 100

    def test_direction_violation_default(self):
        assert compute_risk_score(EventType.DIRECTION_VIOLATION, {}) == 50

    def test_severity_boundaries(self):
        assert severity_for_score(100) == Severity.CRITICAL
        assert severity_for_score(90) == Severity.CRITICAL
        assert severity_for_score(89) == Severity.HIGH
        assert severity_for_score(70) == Severity.HIGH
        assert severity_for_score(69) == Severity.MEDIUM
        assert severity_for_score(40) == Severity.MEDIUM
        assert severity_for_score(39) == Severity.LOW
        assert severity_for_score(0) == Severity.LOW


# ── Lifecycle State Machine ──────────────────────────────────────────────────
class TestLifecycle:
    def test_valid_transitions(self):
        assert can_transition(EventStatus.PENDING, EventStatus.ACTIVE)
        assert can_transition(EventStatus.ACTIVE, EventStatus.SUSTAINED)
        assert can_transition(EventStatus.ACTIVE, EventStatus.RESOLVED)
        assert can_transition(EventStatus.ACTIVE, EventStatus.ESCALATED)
        assert can_transition(EventStatus.SUSTAINED, EventStatus.ESCALATED)
        assert can_transition(EventStatus.ESCALATED, EventStatus.RESOLVED)

    def test_invalid_transitions(self):
        assert not can_transition(EventStatus.RESOLVED, EventStatus.ACTIVE)
        assert not can_transition(EventStatus.SUSTAINED, EventStatus.ACTIVE)
        assert not can_transition(EventStatus.ACTIVE, EventStatus.PENDING)

    def test_validate_raises_on_invalid(self):
        with pytest.raises(InvalidTransition):
            validate_transition(EventStatus.RESOLVED, EventStatus.ACTIVE)

    def test_validate_passes_on_valid(self):
        validate_transition(EventStatus.ACTIVE, EventStatus.RESOLVED)  # exception yok

    def test_terminal_states(self):
        assert is_terminal(EventStatus.RESOLVED)
        assert not is_terminal(EventStatus.ACTIVE)
        assert not is_terminal(EventStatus.ESCALATED)


# ── Dedup + Olay Üretimi ─────────────────────────────────────────────────────
class TestBuildEvents:
    def test_single_violation_creates_event(self):
        engine = EventEngine(dedup_seconds=5.0)
        events = engine.build_events([_violation(risk_hint={"risk_level": "high"})])
        assert len(events) == 1
        e = events[0]
        assert e.camera_id == "cam_01"
        assert e.event_type == EventType.FORBIDDEN_ZONE_ENTRY
        assert e.risk_score == 100
        assert e.severity == Severity.CRITICAL
        assert e.zone_id == "z1"
        assert e.track_ids == [1]
        assert e.metadata == {"risk_level": "high"}
        assert e.started_at.timestamp() == 1000.0

    def test_duplicate_within_window_suppressed(self):
        engine = EventEngine(dedup_seconds=5.0)
        assert len(engine.build_events([_violation(timestamp=1000.0)])) == 1
        assert engine.build_events([_violation(timestamp=1002.0)]) == []

    def test_new_event_after_window_expires(self):
        engine = EventEngine(dedup_seconds=5.0)
        engine.build_events([_violation(timestamp=1000.0)])
        assert len(engine.build_events([_violation(timestamp=1006.0)])) == 1

    def test_sliding_window_extends_on_suppression(self):
        # Sürekli devam eden durum (ör. yangın) tek olay üretmeli: her
        # bastırılan tekrar pencereyi tazeler.
        engine = EventEngine(dedup_seconds=5.0)
        engine.build_events([_violation(timestamp=1000.0)])
        assert engine.build_events([_violation(timestamp=1004.0)]) == []  # tazelendi
        assert engine.build_events([_violation(timestamp=1008.0)]) == []  # 1004'e göre 4 sn
        assert len(engine.build_events([_violation(timestamp=1014.0)])) == 1  # 6 sn boşluk

    def test_different_zone_not_deduped(self):
        engine = EventEngine(dedup_seconds=5.0)
        v1 = _violation(zone_id="z1")
        v2 = _violation(zone_id="z2")
        assert len(engine.build_events([v1, v2])) == 2

    def test_different_tracks_not_deduped(self):
        engine = EventEngine(dedup_seconds=5.0)
        v1 = _violation(track_ids=[1])
        v2 = _violation(track_ids=[2])
        assert len(engine.build_events([v1, v2])) == 2

    def test_different_cameras_not_deduped(self):
        engine = EventEngine(dedup_seconds=5.0)
        v1 = _violation(camera_id="cam_01")
        v2 = _violation(camera_id="cam_02")
        assert len(engine.build_events([v1, v2])) == 2


# ── Tespit-Bazlı İhlal Sentezi (yangın / düşme / KKD) ────────────────────────
class TestDetectionViolations:
    def test_empty_result_no_violations(self):
        engine = EventEngine(dedup_seconds=5.0)
        assert engine.detection_violations(_result()) == []

    def test_fire_detection_produces_fire_violation(self):
        engine = EventEngine(dedup_seconds=5.0)
        result = _result(fire_smoke=[_bbox(class_name="1", conf=0.82)])
        violations = engine.detection_violations(result)
        assert len(violations) == 1
        assert violations[0].event_type == EventType.FIRE
        assert violations[0].risk_hint["confidence"] == 0.82
        assert violations[0].timestamp == 1000.0

    def test_confirmed_fall_produces_fall_violation(self):
        engine = EventEngine(dedup_seconds=5.0)
        pose = PoseResult(bbox=_bbox(), keypoints=[], body_angle=60.0,
                          fall_state=FallState.CONFIRMED, track_id=7)
        violations = engine.detection_violations(_result(poses=[pose]))
        assert len(violations) == 1
        assert violations[0].event_type == EventType.FALL
        assert violations[0].track_ids == [7]
        assert violations[0].risk_hint["sustained"] is False

    def test_sustained_fall_marked_in_hint(self):
        engine = EventEngine(dedup_seconds=5.0)
        pose = PoseResult(bbox=_bbox(), keypoints=[], body_angle=80.0,
                          fall_state=FallState.SUSTAINED, track_id=7)
        violations = engine.detection_violations(_result(poses=[pose]))
        assert violations[0].risk_hint["sustained"] is True

    def test_candidate_fall_ignored(self):
        engine = EventEngine(dedup_seconds=5.0)
        pose = PoseResult(bbox=_bbox(), keypoints=[], body_angle=50.0,
                          fall_state=FallState.CANDIDATE)
        assert engine.detection_violations(_result(poses=[pose])) == []

    def test_ppe_violation_counts_persons(self):
        engine = EventEngine(dedup_seconds=5.0)
        result = _result(ppe=[
            _bbox(class_name="no_hardhat", conf=0.7),
            _bbox(class_name="no_hardhat", conf=0.8),
            _bbox(class_name="helmet", conf=0.9),   # ihlal değil
        ])
        violations = engine.detection_violations(result)
        assert len(violations) == 1
        assert violations[0].event_type == EventType.PPE_VIOLATION
        assert violations[0].risk_hint["person_count"] == 2
        assert violations[0].detected_classes == ["no_hardhat"]

    def test_helmet_only_no_violation(self):
        engine = EventEngine(dedup_seconds=5.0)
        result = _result(ppe=[_bbox(class_name="helmet")])
        assert engine.detection_violations(result) == []


# ── Thumbnail Üretimi (Gün 14) ───────────────────────────────────────────────
def _event_create(risk=70):
    from datetime import datetime, timezone
    return EventCreate(
        camera_id="cam_01",
        event_type=EventType.FORBIDDEN_ZONE_ENTRY,
        severity=Severity.HIGH,
        risk_score=risk,
        started_at=datetime.fromtimestamp(1000.0, tz=timezone.utc),
        zone_id="z1",
        track_ids=[1],
        detected_classes=["person"],
    )


class TestThumbnails:
    def test_render_adds_banner(self):
        result = _result(general=[_bbox(track_id=3)])
        image = render_thumbnail(result, _event_create())
        assert image.shape[0] > result.frame.shape[0]      # banner eklendi
        assert image.shape[1] == result.frame.shape[1]

    def test_save_writes_readable_jpeg(self, tmp_path):
        result = _result(general=[_bbox()])
        path = save_thumbnail("ev_test_001", result, _event_create(), out_dir=str(tmp_path))
        assert path is not None
        assert path.endswith("ev_test_001.jpg")
        image = cv2.imread(path)
        assert image is not None and image.size > 0

    def test_save_failure_returns_none(self, tmp_path):
        # out_dir olarak dizin yerine mevcut bir DOSYA verilir → makedirs
        # başarısız olur; olay kaydını engellememek için None dönmeli.
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x")
        result = _result()
        path = save_thumbnail("ev_test_002", result, _event_create(), out_dir=str(blocker))
        assert path is None


# ── Uçtan Uca process() — DB katmanı sahte oturumla izole edilir ─────────────
class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_process_persists_and_returns_ids(monkeypatch, tmp_path):
    from app import database
    from app.config import settings
    from app.db import crud

    created = []

    async def fake_create_event(db, data, *, event_id, thumbnail_path=None):
        created.append((data, event_id, thumbnail_path))

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(crud, "create_event", fake_create_event)
    monkeypatch.setattr(settings, "thumbnails_dir", str(tmp_path))

    engine = EventEngine(dedup_seconds=5.0)
    result = _result(fire_smoke=[_bbox(class_name="1", conf=0.9)])
    rule_violation = _violation(risk_hint={"risk_level": "high"})

    event_ids = await engine.process(result, [rule_violation])

    # 1 kural ihlali + 1 yangın tespiti = 2 olay
    assert len(event_ids) == 2
    assert len(created) == 2
    types = {c[0].event_type for c in created}
    assert types == {EventType.FORBIDDEN_ZONE_ENTRY, EventType.FIRE}
    # Thumbnail üretildi ve event ID ile isimlendirildi
    for data, event_id, thumbnail_path in created:
        assert thumbnail_path is not None
        assert event_id in thumbnail_path


@pytest.mark.asyncio
async def test_process_db_failure_does_not_crash(monkeypatch, tmp_path):
    from app import database
    from app.config import settings

    class _BrokenSession:
        async def __aenter__(self):
            raise ConnectionError("db down")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: _BrokenSession())
    monkeypatch.setattr(settings, "thumbnails_dir", str(tmp_path))

    engine = EventEngine(dedup_seconds=5.0)
    event_ids = await engine.process(_result(), [_violation()])
    assert event_ids == []  # olay yazılamadı ama exception fırlamadı
