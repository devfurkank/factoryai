"""
Poz Dedektörü ve Düşme State Machine.
YOLOv8-pose ile 17 COCO keypoint çıkarımı + düşme analizi.

State Machine: NORMAL → CANDIDATE (açı > 45°) → CONFIRMED (3 frame) → SUSTAINED (30 sn)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import structlog

from app.detection.types import BBox, FallState, PoseResult

log = structlog.get_logger()

# COCO Keypoint indeksleri
KP_NOSE          = 0
KP_LEFT_SHOULDER = 5
KP_RIGHT_SHOULDER = 6
KP_LEFT_HIP      = 11
KP_RIGHT_HIP     = 12
KP_LEFT_KNEE     = 13
KP_RIGHT_KNEE    = 14
KP_LEFT_ANKLE    = 15
KP_RIGHT_ANKLE   = 16

# Düşme eşikleri
FALL_ANGLE_THRESHOLD   = 45.0   # gövde dikeyden bu açıyı aşarsa CANDIDATE
FALL_CONFIRM_FRAMES    = 3      # CANDIDATE → CONFIRMED
FALL_SUSTAINED_SECONDS = 30.0   # CONFIRMED + 30 sn hareketsiz → SUSTAINED
TRACK_STALE_SECONDS    = 10.0   # Bu kadar süre görülmemiş track temizlenir


@dataclass
class _FallTrack:
    state: FallState = FallState.NORMAL
    candidate_frames: int = 0
    confirmed_at: Optional[float] = None
    last_seen: float = field(default_factory=time.time)


class PoseDetector:
    """
    YOLOv8-pose model wrapper + kişi başına düşme state machine.
    """

    def __init__(self, model, conf: float = 0.4):
        self._model = model
        self._conf = conf
        self._tracks: Dict[int, _FallTrack] = {}  # track_id → FallTrack

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[PoseResult]]:
        if not frames or self._model is None:
            return [[] for _ in frames]
        try:
            results = self._model(frames, conf=self._conf, verbose=False, stream=False)
            return [self._parse(r) for r in results]
        except Exception as exc:
            log.error("pose_detector.batch_error", error=str(exc))
            return [[] for _ in frames]

    def update_fall_states(self, poses: List[PoseResult]) -> List[PoseResult]:
        """Her kişi için düşme state machine'ini günceller."""
        now = time.time()
        for pose in poses:
            # Track ID yoksa merkez koordinatından yaklaşık ID türet
            if pose.track_id is None:
                cx = int(pose.bbox.center[0]) // 50
                cy = int(pose.bbox.center[1]) // 50
                pose.track_id = abs(hash((cx, cy))) % 100_000

            tid = pose.track_id
            if tid not in self._tracks:
                self._tracks[tid] = _FallTrack()

            track = self._tracks[tid]
            track.last_seen = now
            is_falling = pose.body_angle > FALL_ANGLE_THRESHOLD

            prev_state = track.state

            if track.state == FallState.NORMAL:
                if is_falling:
                    track.candidate_frames = 1
                    track.state = FallState.CANDIDATE

            elif track.state == FallState.CANDIDATE:
                if is_falling:
                    track.candidate_frames += 1
                    if track.candidate_frames >= FALL_CONFIRM_FRAMES:
                        track.state = FallState.CONFIRMED
                        track.confirmed_at = now
                        log.warning("fall.confirmed",
                                    track_id=tid, angle=round(pose.body_angle, 1))
                else:
                    track.state = FallState.NORMAL
                    track.candidate_frames = 0

            elif track.state == FallState.CONFIRMED:
                elapsed = now - (track.confirmed_at or now)
                if elapsed >= FALL_SUSTAINED_SECONDS:
                    track.state = FallState.SUSTAINED
                    log.warning("fall.sustained", track_id=tid, seconds=round(elapsed, 0))
                elif not is_falling:
                    # Kişi kalktı
                    track.state = FallState.NORMAL
                    track.candidate_frames = 0
                    track.confirmed_at = None
                    log.info("fall.recovered", track_id=tid)

            elif track.state == FallState.SUSTAINED:
                if not is_falling:
                    track.state = FallState.NORMAL
                    track.candidate_frames = 0
                    track.confirmed_at = None
                    log.info("fall.recovered_from_sustained", track_id=tid)

            if track.state != prev_state:
                log.debug("fall.state_change",
                          track_id=tid, prev=prev_state, next=track.state,
                          angle=round(pose.body_angle, 1))

            pose.fall_state = track.state

        # Eski track'leri temizle
        stale = [tid for tid, t in self._tracks.items()
                 if now - t.last_seen > TRACK_STALE_SECONDS]
        for tid in stale:
            del self._tracks[tid]

        return poses

    # ── Yardımcı Fonksiyonlar ─────────────────────────────────────────────────
    def _parse(self, result) -> List[PoseResult]:
        pose_results: List[PoseResult] = []
        if result.boxes is None or result.keypoints is None:
            return pose_results

        kp_data_all = result.keypoints.data  # shape: (N, 17, 3)

        for i, box in enumerate(result.boxes):
            cls_id = int(box.cls.item())
            # Sadece person sınıfını işle
            if result.names.get(cls_id, "").lower() != "person":
                continue

            xyxy = box.xyxy[0].cpu().numpy()
            bbox = BBox(
                x1=float(xyxy[0]),
                y1=float(xyxy[1]),
                x2=float(xyxy[2]),
                y2=float(xyxy[3]),
                confidence=float(box.conf.item()),
                class_id=cls_id,
                class_name="person",
            )

            kp = kp_data_all[i].cpu().numpy()  # (17, 3)
            keypoints = kp.tolist()
            angle = _compute_body_angle(kp)

            pose_results.append(PoseResult(
                bbox=bbox,
                keypoints=keypoints,
                body_angle=angle,
                fall_state=FallState.NORMAL,
            ))

        return pose_results


def _compute_body_angle(kp: np.ndarray) -> float:
    """
    Omuz–kalça vektörünün dikeyden sapma açısını hesaplar.
    kp: (17, 3) ndarray — [[x, y, conf], ...]
    Döndürür: 0–90 derece (0 = dik, 90 = yatay)
    """
    try:
        l_sh = kp[KP_LEFT_SHOULDER]
        r_sh = kp[KP_RIGHT_SHOULDER]
        l_hip = kp[KP_LEFT_HIP]
        r_hip = kp[KP_RIGHT_HIP]

        sh_conf  = max(l_sh[2], r_sh[2])
        hip_conf = max(l_hip[2], r_hip[2])
        if sh_conf < 0.2 or hip_conf < 0.2:
            return 0.0

        # Ağırlıklı orta nokta (güven skoruna göre)
        if l_sh[2] > 0.2 and r_sh[2] > 0.2:
            mid_sh = (l_sh[:2] + r_sh[:2]) / 2
        elif l_sh[2] > 0.2:
            mid_sh = l_sh[:2]
        else:
            mid_sh = r_sh[:2]

        if l_hip[2] > 0.2 and r_hip[2] > 0.2:
            mid_hip = (l_hip[:2] + r_hip[:2]) / 2
        elif l_hip[2] > 0.2:
            mid_hip = l_hip[:2]
        else:
            mid_hip = r_hip[:2]

        # Omuzdan kalçaya vektör (resim koordinatında y aşağı artar)
        dx = mid_sh[0] - mid_hip[0]
        dy = mid_hip[1] - mid_sh[1]  # Pozitif = omuz yukarıda

        # Dikeyden açı: dik duruşta dx≈0, dy>0 → açı≈0
        angle = abs(np.degrees(np.arctan2(abs(dx), max(abs(dy), 1e-6))))
        return float(min(angle, 90.0))
    except Exception:
        return 0.0
