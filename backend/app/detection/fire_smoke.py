"""
Yangın / Duman Dedektörü — Temporal smoothing ile yanlış alarm azaltma.
Ardışık 5 frame içinde en az 3'ünde tespit → onaylı alarm.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

import numpy as np
import structlog

from app.detection.types import BBox

log = structlog.get_logger()


class FireSmokeDetector:
    """
    fire_detection.pt ile yangın/duman tespiti.
    Temporal onay: HISTORY_SIZE frame içinde MIN_DETECTIONS tespit → gerçek alarm.
    """

    HISTORY_SIZE = 5     # Geçmişte tutulacak frame sayısı
    MIN_DETECTIONS = 3   # Onay için gerekli minimum tespit sayısı

    def __init__(self, model, conf: float = 0.5):
        self._model = model
        self._conf = conf
        # Kamera başına tespit geçmişi: camera_id → deque[bool]
        self._history: Dict[str, deque] = {}

    def detect_batch(
        self, frames_with_ids: List[Tuple[str, np.ndarray]]
    ) -> List[List[BBox]]:
        """
        frames_with_ids: [(camera_id, frame), ...]
        Döndürür: temporal olarak onaylanmış BBox listesi (kamera başına)
        """
        if not frames_with_ids or self._model is None:
            return [[] for _ in frames_with_ids]

        camera_ids = [f[0] for f in frames_with_ids]
        raw_frames = [f[1] for f in frames_with_ids]

        try:
            results = self._model(raw_frames, conf=self._conf, verbose=False, stream=False)
        except Exception as exc:
            log.error("fire_smoke.batch_error", error=str(exc))
            return [[] for _ in frames_with_ids]

        confirmed: List[List[BBox]] = []
        for camera_id, result in zip(camera_ids, results):
            raw_boxes = self._parse(result)
            detected_now = len(raw_boxes) > 0

            hist = self._history.setdefault(camera_id, deque(maxlen=self.HISTORY_SIZE))
            hist.append(detected_now)

            # Temporal onay: son HISTORY_SIZE frame'de MIN_DETECTIONS tespit varsa gerçek
            if sum(hist) >= self.MIN_DETECTIONS:
                confirmed.append(raw_boxes)
                if detected_now:
                    log.warning(
                        "fire_smoke.alarm_confirmed",
                        camera_id=camera_id,
                        classes=[b.class_name for b in raw_boxes],
                        confidence=[round(b.confidence, 2) for b in raw_boxes],
                    )
            else:
                confirmed.append([])

        return confirmed

    def _parse(self, result) -> List[BBox]:
        boxes: List[BBox] = []
        if result.boxes is None:
            return boxes
        for box in result.boxes:
            cls_id = int(box.cls.item())
            cls_name = result.names.get(cls_id, str(cls_id)).lower().strip()
            xyxy = box.xyxy[0].cpu().numpy()
            boxes.append(BBox(
                x1=float(xyxy[0]),
                y1=float(xyxy[1]),
                x2=float(xyxy[2]),
                y2=float(xyxy[3]),
                confidence=float(box.conf.item()),
                class_id=cls_id,
                class_name=cls_name,
            ))
        return boxes

    def reset_camera(self, camera_id: str):
        """Kamera geçmişini sıfırla (kamera yeniden bağlanırsa)."""
        self._history.pop(camera_id, None)
