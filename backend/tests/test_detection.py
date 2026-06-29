"""
Detection modülü testleri — Faz 2.
Model yüklenmeden (mock-free) çalışan birim testler.
"""
import numpy as np
import pytest

from app.detection.types import BBox, DetectionResult, FallState, PoseResult
from app.detection.pose import _compute_body_angle, FALL_ANGLE_THRESHOLD, PoseDetector
from app.detection.fire_smoke import FireSmokeDetector
from app.detection.yolo import PPEDetector, hardhat_is_on


# ── BBox testleri ──────────────────────────────────────────────────────────────
class TestBBox:
    def test_center(self):
        b = BBox(x1=0, y1=0, x2=100, y2=80, confidence=0.9, class_id=0, class_name="person")
        assert b.center == (50.0, 40.0)

    def test_area(self):
        b = BBox(x1=10, y1=10, x2=110, y2=60, confidence=0.8, class_id=0, class_name="person")
        assert b.area == 5000.0


# ── DetectionResult testleri ──────────────────────────────────────────────────
class TestDetectionResult:
    def _make_result(self, general=None, ppe=None, fire=None, poses=None):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        return DetectionResult(
            camera_id="cam_01",
            timestamp=1000.0,
            frame=frame,
            general=general or [],
            ppe=ppe or [],
            fire_smoke=fire or [],
            poses=poses or [],
        )

    def test_person_count(self):
        r = self._make_result(general=[
            BBox(0, 0, 50, 100, 0.9, 0, "person"),
            BBox(0, 0, 50, 100, 0.8, 0, "person"),
            BBox(0, 0, 100, 80, 0.7, 2, "vehicle"),
        ])
        assert r.person_count == 2

    def test_has_fire(self):
        r = self._make_result(fire=[BBox(0, 0, 50, 50, 0.85, 0, "fire")])
        assert r.has_fire is True
        assert r.has_smoke is False

    def test_has_ppe_violation(self):
        r = self._make_result(ppe=[BBox(0, 0, 50, 50, 0.75, 1, "no_hardhat")])
        assert r.has_ppe_violation is True

    def test_no_ppe_violation_when_hardhat(self):
        r = self._make_result(ppe=[BBox(0, 0, 50, 50, 0.9, 0, "hardhat")])
        assert r.has_ppe_violation is False

    def test_summary_keys(self):
        r = self._make_result()
        s = r.summary()
        assert "camera_id" in s
        assert "persons" in s
        assert "fire" in s
        assert "fall" in s


# ── Düşme açısı testleri ──────────────────────────────────────────────────────
class TestBodyAngle:
    def _make_kp(self, l_sh, r_sh, l_hip, r_hip, conf=0.9):
        """17 keypoint array oluşturur, sadece omuz ve kalçayı ayarlar."""
        kp = np.zeros((17, 3), dtype=float)
        kp[5] = [l_sh[0], l_sh[1], conf]
        kp[6] = [r_sh[0], r_sh[1], conf]
        kp[11] = [l_hip[0], l_hip[1], conf]
        kp[12] = [r_hip[0], r_hip[1], conf]
        return kp

    def test_upright_person_low_angle(self):
        # Omuz yukarıda, kalça aşağıda (dik duruş)
        kp = self._make_kp(l_sh=(100, 50), r_sh=(120, 50),
                           l_hip=(100, 150), r_hip=(120, 150))
        angle = _compute_body_angle(kp)
        assert angle < FALL_ANGLE_THRESHOLD, f"Dik durumda açı çok büyük: {angle}"

    def test_lying_person_high_angle(self):
        # Omuz ve kalça yatay hizada (yatmış kişi)
        kp = self._make_kp(l_sh=(50, 100), r_sh=(70, 100),
                           l_hip=(200, 105), r_hip=(220, 105))
        angle = _compute_body_angle(kp)
        assert angle > FALL_ANGLE_THRESHOLD, f"Yatmış durumda açı çok küçük: {angle}"

    def test_low_confidence_returns_zero(self):
        kp = np.zeros((17, 3), dtype=float)
        # Tüm keypoint güven skoru 0
        angle = _compute_body_angle(kp)
        assert angle == 0.0


# ── KKD Çapraz Karşılaştırma Testleri ────────────────────────────────────────
class TestHardhatIsOn:
    """
    hardhat_is_on(): baret merkezi kişinin baş bölgesinde mi?
    Referans: hard_hat_ornek/utils/bbox_utils.py
    """

    def _person(self, x1=100, y1=50, x2=200, y2=250) -> BBox:
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=0.9, class_id=0, class_name="person")

    def _helmet(self, cx, cy, size=20) -> BBox:
        return BBox(x1=cx-size, y1=cy-size, x2=cx+size, y2=cy+size,
                    confidence=0.85, class_id=0, class_name="helmet")

    def test_helmet_on_head_returns_true(self):
        # Kişi: x100–200, y50–250 → width=100, height=200
        person = self._person(100, 50, 200, 250)
        # Baş merkezi: x=150 (orta), y=60 (üst bölge)
        helmet = self._helmet(cx=150, cy=60, size=15)
        assert hardhat_is_on(person, helmet, frame_width=640) is True

    def test_helmet_far_below_returns_false(self):
        # Baret yerde (kişinin altında)
        person = self._person(100, 50, 200, 250)
        helmet = self._helmet(cx=150, cy=240, size=15)
        assert hardhat_is_on(person, helmet, frame_width=640) is False

    def test_helmet_beside_person_returns_false(self):
        # Baret yanında
        person = self._person(100, 50, 200, 250)
        helmet = self._helmet(cx=350, cy=60, size=15)
        assert hardhat_is_on(person, helmet, frame_width=640) is False


class TestPPECheckViolations:
    """PPEDetector.check_violations(): baretsiz kişi → no_hardhat ihlali."""

    def _person(self, x1=100, y1=50, x2=200, y2=250) -> BBox:
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=0.9, class_id=0, class_name="person")

    def _helmet(self, cx, cy, size=15) -> BBox:
        return BBox(x1=cx-size, y1=cy-size, x2=cx+size, y2=cy+size,
                    confidence=0.85, class_id=0, class_name="helmet")

    def test_person_without_helmet_gets_violation(self):
        detector = PPEDetector(model=None)
        persons = [self._person()]
        helmets = []  # Baret yok
        violations = detector.check_violations(persons, helmets, frame_width=640)
        assert len(violations) == 1
        assert violations[0].class_name == "no_hardhat"

    def test_person_with_helmet_no_violation(self):
        detector = PPEDetector(model=None)
        persons = [self._person(100, 50, 200, 250)]
        helmets = [self._helmet(cx=150, cy=60)]  # Başta baret var
        violations = detector.check_violations(persons, helmets, frame_width=640)
        assert len(violations) == 0

    def test_two_persons_one_without_helmet(self):
        detector = PPEDetector(model=None)
        persons = [
            self._person(100, 50, 200, 250),   # baret var
            self._person(400, 50, 500, 250),   # baret yok
        ]
        helmets = [self._helmet(cx=150, cy=60)]  # sadece ilk kişi için
        violations = detector.check_violations(persons, helmets, frame_width=640)
        assert len(violations) == 1
        assert violations[0].x1 == 400  # ikinci kişi ihlal

    def test_no_persons_no_violations(self):
        detector = PPEDetector(model=None)
        violations = detector.check_violations([], [], frame_width=640)
        assert violations == []

    def test_violation_bbox_at_head_area(self):
        """İhlal bbox'ı kişinin baş bölgesinde olmalı (üst %30)."""
        detector = PPEDetector(model=None)
        person = self._person(100, 50, 200, 250)  # height = 200
        violations = detector.check_violations([person], [], frame_width=640)
        assert len(violations) == 1
        v = violations[0]
        expected_y2 = 50 + 200 * 0.30  # y1 + height * 0.30 = 50 + 60 = 110
        assert abs(v.y2 - expected_y2) < 1.0


# ── Temporal smoothing testi (model olmadan) ──────────────────────────────────
class TestFireSmokeTemporalSmoothing:
    def test_alarm_requires_min_detections(self):
        """Yeterli tespit olmadan alarm üretilmez."""
        from collections import deque
        detector = FireSmokeDetector(model=None, conf=0.5)
        detector._history["cam_01"] = deque([True, True, False, False, False], maxlen=5)
        # 2 True var, minimum 3 gerekiyor → alarm yok
        assert sum(detector._history["cam_01"]) < detector.MIN_DETECTIONS

    def test_alarm_triggered_at_threshold(self):
        """MIN_DETECTIONS kadar True olduğunda alarm eşiği aşılır."""
        from collections import deque
        detector = FireSmokeDetector(model=None, conf=0.5)
        detector._history["cam_01"] = deque([True, True, True, False, False], maxlen=5)
        # 3 True var → alarm eşiği aşıldı
        assert sum(detector._history["cam_01"]) >= detector.MIN_DETECTIONS

    def test_reset_clears_history(self):
        """reset_camera geçmişi temizler."""
        from collections import deque
        detector = FireSmokeDetector(model=None, conf=0.5)
        detector._history["cam_01"] = deque([True, True, True], maxlen=5)
        detector.reset_camera("cam_01")
        assert "cam_01" not in detector._history


# ── FallState state machine testi ─────────────────────────────────────────────
class TestFallStateMachine:
    def test_candidate_to_confirmed_after_n_frames(self):
        detector = PoseDetector(model=None)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Yüksek açılı (düşmüş) PoseResult'lar oluştur
        def make_pose(track_id: int) -> PoseResult:
            bbox = BBox(100, 100, 200, 300, 0.9, 0, "person", track_id=track_id)
            return PoseResult(
                bbox=bbox,
                keypoints=[[0, 0, 0]] * 17,
                body_angle=80.0,  # FALL_ANGLE_THRESHOLD (45°) üzeri
                fall_state=FallState.NORMAL,
                track_id=track_id,
            )

        # 3 frame geçince CONFIRMED olmalı
        from app.detection.pose import FALL_CONFIRM_FRAMES
        for i in range(FALL_CONFIRM_FRAMES):
            poses = [make_pose(track_id=42)]
            updated = detector.update_fall_states(poses)
            # Son frame'de CONFIRMED bekliyoruz
            if i < FALL_CONFIRM_FRAMES - 1:
                assert updated[0].fall_state in (FallState.CANDIDATE, FallState.NORMAL)
            else:
                assert updated[0].fall_state == FallState.CONFIRMED

    def test_recovery_resets_state(self):
        detector = PoseDetector(model=None)
        # Önce CANDIDATE durumuna getir
        from app.detection.pose import _FallTrack
        detector._tracks[99] = _FallTrack(
            state=FallState.CONFIRMED, candidate_frames=3
        )
        # Normal açılı pose ver → iyileşme
        bbox = BBox(100, 100, 200, 300, 0.9, 0, "person", track_id=99)
        pose = PoseResult(bbox=bbox, keypoints=[[0, 0, 0]] * 17,
                          body_angle=10.0, fall_state=FallState.CONFIRMED, track_id=99)
        updated = detector.update_fall_states([pose])
        assert updated[0].fall_state == FallState.NORMAL
