"""
YOLOv8 Dedektörler — Genel (person/araç) ve KKD (baret) tespiti.

KKD Mimarisi (referans projeden uyarlama):
  - last_hardhat_200_epochs.pt: yalnızca "helmet" sınıfını tespit eder (1 class)
  - yolov8x.pt: person/araç tespiti (COCO, class 0 = person)
  - İhlal tespiti: hardhat_is_on() ile kişi × baret çapraz karşılaştırma
    → Üst bölgesinde baret olmayan kişi = "no_hardhat" ihlali
"""
from __future__ import annotations

import structlog
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.detection.types import BBox

log = structlog.get_logger()

# COCO class ID → fabrika güvenliği etiketleri
COCO_FACTORY_MAP: Dict[int, str] = {
    0: "person",
    2: "vehicle",   # car
    3: "vehicle",   # motorcycle
    5: "vehicle",   # bus
    7: "vehicle",   # truck
}


class GeneralDetector:
    """
    YOLOv8x COCO model ile insan ve araç tespiti.
    Referans proje: PersonTracker('yolov8x')
    """

    def __init__(self, model, conf: float = 0.4):
        self._model = model
        self._conf = conf
        self._classes = list(COCO_FACTORY_MAP.keys())

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[BBox]]:
        if not frames or self._model is None:
            return [[] for _ in frames]
        try:
            results = self._model(
                frames,
                conf=self._conf,
                classes=self._classes,
                verbose=False,
                stream=False,
            )
            return [self._parse(r) for r in results]
        except Exception as exc:
            log.error("general_detector.batch_error", error=str(exc))
            return [[] for _ in frames]

    def _parse(self, result) -> List[BBox]:
        boxes: List[BBox] = []
        if result.boxes is None:
            return boxes
        for box in result.boxes:
            cls_id = int(box.cls.item())
            cls_name = COCO_FACTORY_MAP.get(
                cls_id, result.names.get(cls_id, str(cls_id))
            )
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


# ── Baret İhlal Mantığı ───────────────────────────────────────────────────────
# Referans: hard_hat_ornek/utils/bbox_utils.py::hardhat_is_on()

def hardhat_is_on(person: BBox, helmet: BBox, frame_width: int) -> bool:
    """
    Bir baret (helmet bbox) kişinin başında mı?

    Kişinin 'güvenli alan' hesabı:
      x: kişi merkezinin ± (person_width / 6) etrafı
      y: (kişi üstü − baret_yüksekliği/2)  →  (kişi altı − kişi_yüksekliği * 3/4)

    Baret merkezi bu alanın içindeyse baret takılıdır.
    """
    p_w = person.width
    p_h = person.height
    h_h = helmet.height

    x1 = max(0.0,         person.x1 + p_w / 2 - p_w / 6)
    x2 = min(float(frame_width), person.x1 + p_w / 2 + p_w / 6)
    y1 = max(0.0,         person.y1 - h_h / 2)
    y2 = max(0.0,         person.y2 - p_h * 3 / 4)

    hx, hy = helmet.center
    return (x1 <= hx <= x2) and (y1 <= hy <= y2)


class PPEDetector:
    """
    KKD (Kişisel Koruyucu Donanım) dedektörü.

    last_hardhat_200_epochs.pt yalnızca "helmet" sınıfını öğrenmiş (nc: 1).
    İhlal (no_hardhat) baretlerin yokluğundan çıkarsanır.

    Kullanım:
      1. helmets = ppe_detector.detect_helmets_batch(frames)
      2. violations = ppe_detector.check_violations(persons, helmets[i], frame_w)
         → persons_without_helmet listesi (class_name = "no_hardhat")
    """

    def __init__(self, model, conf: float = 0.4):
        self._model = model
        self._conf = conf

    def detect_helmets_batch(self, frames: List[np.ndarray]) -> List[List[BBox]]:
        """Her frame için tespit edilen baret bbox'larını döndürür (class = "helmet")."""
        if not frames or self._model is None:
            return [[] for _ in frames]
        try:
            results = self._model(frames, conf=self._conf, verbose=False, stream=False)
            return [self._parse(r) for r in results]
        except Exception as exc:
            log.error("ppe_detector.batch_error", error=str(exc))
            return [[] for _ in frames]

    def check_violations(
        self,
        persons: List[BBox],
        helmets: List[BBox],
        frame_width: int,
    ) -> List[BBox]:
        """
        Her kişi için baret takılı mı kontrol eder.
        Baretsiz her kişi için baş bölgesinde sentetik 'no_hardhat' BBox üretir.
        """
        violations: List[BBox] = []
        for person in persons:
            wearing = any(hardhat_is_on(person, h, frame_width) for h in helmets)
            if not wearing:
                # Baş bölgesini (üst %30) ihlal alanı olarak işaretle
                head_y2 = person.y1 + person.height * 0.30
                violations.append(BBox(
                    x1=person.x1,
                    y1=person.y1,
                    x2=person.x2,
                    y2=head_y2,
                    confidence=1.0,      # Kesin ihlal — baret yokluğundan çıkarsandı
                    class_id=-1,
                    class_name="no_hardhat",
                ))
        return violations

    def _parse(self, result) -> List[BBox]:
        boxes: List[BBox] = []
        if result.boxes is None:
            return boxes
        for box in result.boxes:
            cls_id = int(box.cls.item())
            # Modelin tek sınıfı: 0 = helmet
            cls_name = result.names.get(cls_id, "helmet").lower().strip()
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
