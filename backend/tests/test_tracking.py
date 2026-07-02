"""Tracking modülü testleri — Faz 3 (ultralytics BYTETracker adaptörü).

Not: Eşleştirme/Kalman/lifecycle mantığının kendisi ultralytics.trackers'ta
(iyi test edilmiş, üçüncü taraf kütüphane). Buradaki testler SADECE bizim
adaptör katmanımızın (BBox ↔ ultralytics I/O dönüşümü, track_id'nin BBox'a
yerinde yazılması, kamera başına izolasyon) doğru çalıştığını doğrular.
"""
import pytest

from app.detection.types import BBox
from app.tracking.bytetrack import ByteTracker
from app.tracking.engine import TrackingEngine
from app.tracking.types import TrackState


def _det(x1, y1, x2, y2, conf=0.9, class_name="person"):
    return BBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf, class_id=0, class_name=class_name)


class TestByteTrackerAdapter:
    def test_first_detection_gets_track_id_immediately(self):
        # ultralytics BYTETracker: frame_id == 1 özel durumunda yeni track'ler
        # anında aktifleşir (bkz. bytetrack.py modül docstring'i).
        tracker = ByteTracker(max_age=3)
        det = _det(0, 0, 50, 50)
        tracked = tracker.update([det])
        assert len(tracked) == 1
        assert tracked[0].state == TrackState.CONFIRMED
        assert tracked[0].class_name == "person"
        assert det.track_id == tracked[0].track_id  # BBox.track_id yerinde atanmalı

    def test_bbox_roundtrip_close_to_input_on_first_frame(self):
        tracker = ByteTracker()
        det = _det(100, 50, 200, 250)
        tracked = tracker.update([det])
        x1, y1, x2, y2 = tracked[0].bbox
        assert x1 == pytest.approx(100, abs=1.0)
        assert y1 == pytest.approx(50, abs=1.0)
        assert x2 == pytest.approx(200, abs=1.0)
        assert y2 == pytest.approx(250, abs=1.0)

    def test_track_id_persists_across_slightly_moved_frames(self):
        tracker = ByteTracker()
        det1 = _det(100, 100, 150, 150)
        tid = tracker.update([det1])[0].track_id

        det2 = _det(103, 101, 153, 151)  # birkaç piksel kaymış
        tracked2 = tracker.update([det2])
        assert len(tracked2) == 1
        assert tracked2[0].track_id == tid
        assert det2.track_id == tid

    def test_class_name_preserved(self):
        tracker = ByteTracker()
        det = _det(0, 0, 50, 100, class_name="vehicle")
        tracked = tracker.update([det])
        assert tracked[0].class_name == "vehicle"

    def test_mixed_classes_tracked_independently(self):
        tracker = ByteTracker()
        person = _det(0, 0, 50, 100, class_name="person")
        vehicle = _det(500, 500, 600, 560, class_name="vehicle")
        tracked = tracker.update([person, vehicle])
        assert len(tracked) == 2
        names = {t.class_name for t in tracked}
        assert names == {"person", "vehicle"}

    def test_empty_detections_does_not_crash(self):
        tracker = ByteTracker()
        assert tracker.update([]) == []

    def test_empty_then_detection_eventually_confirms(self):
        # İlk çağrı boş geçtiği için "frame_id==1 anında aktifleşir" özel
        # durumu burada kullanılmış olur; bu yüzden ilk tespit hemen değil,
        # bir sonraki eşleşmede (2. tespit çağrısında) track olarak görünür.
        tracker = ByteTracker()
        tracker.update([])
        tracker.update([_det(0, 0, 50, 50)])
        tracked = tracker.update([_det(2, 1, 52, 51)])
        assert len(tracked) == 1

    def test_low_confidence_alone_does_not_create_track(self):
        tracker = ByteTracker(high_thresh=0.5, low_thresh=0.1)
        det = _det(0, 0, 50, 50, conf=0.3)  # high_thresh altında, eşleşecek track de yok
        tracked = tracker.update([det])
        assert tracked == []

    def test_active_tracks_reflects_last_update_without_new_frame(self):
        tracker = ByteTracker()
        tracker.update([_det(0, 0, 50, 50)])
        active = tracker.active_tracks()
        assert len(active) == 1

    def test_active_tracks_before_any_update_is_empty(self):
        tracker = ByteTracker()
        assert tracker.active_tracks() == []


class TestTrackingEngine:
    def test_per_camera_isolation(self):
        engine = TrackingEngine()
        det_a = _det(0, 0, 50, 50)
        det_b = _det(0, 0, 50, 50)
        tracked_a = engine.update("cam_a", [det_a])
        tracked_b = engine.update("cam_b", [det_b])
        assert len(tracked_a) == 1
        assert len(tracked_b) == 1
        # Her kamera bağımsız kendi ByteTracker'ını kullanmalı (ikisi de 1'den başlar)
        assert tracked_a[0].track_id == tracked_b[0].track_id == 1

    def test_get_active_tracks_without_new_frame(self):
        engine = TrackingEngine()
        engine.update("cam_a", [_det(0, 0, 50, 50)])
        active = engine.get_active_tracks("cam_a")
        assert len(active) == 1

    def test_get_active_tracks_unknown_camera_returns_empty(self):
        engine = TrackingEngine()
        assert engine.get_active_tracks("cam_unknown") == []
