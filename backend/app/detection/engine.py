"""
Detection Engine — Faz 2 implementasyonu.
Kamera frame'lerini alır, 4 YOLOv8 modeli ile batch inference yapar
ve DetectionResult'ları downstream kuyrukta yayınlar.

Mimari:
  frame_queue (asyncio) → batcher → [thread] inference → result_queue (asyncio)
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog

from app.config import settings
from app.detection.types import DetectionResult
from app.detection.models import model_registry
from app.detection.yolo import GeneralDetector, PPEDetector
from app.detection.fire_smoke import FireSmokeDetector
from app.detection.pose import PoseDetector

log = structlog.get_logger()

# Tek worker: GPU inference tek thread'de seri çalışır (CUDA thread-safety)
_inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="det-inf")

# Annotation için opsiyonel import
try:
    import cv2 as _cv2
    _CV2_OK = True
except ImportError:
    _CV2_OK = False


class DetectionEngine:
    """
    Batch frame inference orkestratörü.
    """

    def __init__(self):
        self.result_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._running = False
        self._models_loaded = False

        self._general: Optional[GeneralDetector] = None
        self._ppe: Optional[PPEDetector] = None
        self._fire: Optional[FireSmokeDetector] = None
        self._pose: Optional[PoseDetector] = None

        # Kamera başına en son tespit sonucu (debug/snapshot endpoint'leri için)
        self._latest_results: Dict[str, DetectionResult] = {}

        # Metrikler
        self._frame_count = 0
        self._batch_count = 0
        self._metrics_start = time.time()

    # ── Model Yükleme (senkron, thread'de çalışır) ────────────────────────────
    def _load_models(self):
        log.info("detection.engine.loading_models", models_dir=settings.models_dir)
        model_registry.load_all(
            models_dir=settings.models_dir,
            general_model=settings.yolo_general_model,
            pose_model=settings.yolo_pose_model,
            ppe_model=settings.yolo_ppe_model,
            fire_model=settings.yolo_fire_model,
        )

        if model_registry.general:
            self._general = GeneralDetector(model_registry.general,
                                            conf=settings.detection_confidence)
        if model_registry.ppe:
            self._ppe = PPEDetector(model_registry.ppe,
                                    conf=settings.detection_confidence)
        if model_registry.fire:
            self._fire = FireSmokeDetector(model_registry.fire, conf=0.5)
        if model_registry.pose:
            self._pose = PoseDetector(model_registry.pose,
                                      conf=settings.detection_confidence)

        self._models_loaded = True
        log.info(
            "detection.engine.ready",
            general=self._general is not None,
            ppe=self._ppe is not None,
            fire=self._fire is not None,
            pose=self._pose is not None,
        )

    # ── Batch Inference (senkron, thread'de çalışır) ──────────────────────────
    def _run_batch(
        self, batch: List[Tuple[str, np.ndarray, float]]
    ) -> List[DetectionResult]:
        if not self._models_loaded or not batch:
            return []

        cam_ids   = [b[0] for b in batch]
        frames    = [b[1] for b in batch]
        times     = [b[2] for b in batch]

        # Ön-allocation
        results: List[DetectionResult] = [
            DetectionResult(camera_id=cam_ids[i], timestamp=times[i], frame=frames[i])
            for i in range(len(batch))
        ]

        # 1. Genel tespit: person, araç
        if self._general:
            try:
                for i, boxes in enumerate(self._general.detect_batch(frames)):
                    results[i].general = boxes
            except Exception as exc:
                log.error("detection.general.error", error=str(exc))

        # 2. KKD tespiti: baret tespiti → kişi çapraz karşılaştırma → ihlal sentezi
        if self._ppe:
            try:
                helmet_batches = self._ppe.detect_helmets_batch(frames)
                for i, helmets in enumerate(helmet_batches):
                    frame_w = frames[i].shape[1]
                    persons = [b for b in results[i].general if b.class_name == "person"]
                    violations = self._ppe.check_violations(persons, helmets, frame_w)
                    # ppe alanı: tespit edilen baretler + sentetik ihlaller
                    results[i].ppe = helmets + violations
            except Exception as exc:
                log.error("detection.ppe.error", error=str(exc))

        # 3. Yangın/duman: temporal onaylı
        if self._fire:
            try:
                fire_input = list(zip(cam_ids, frames))
                for i, boxes in enumerate(self._fire.detect_batch(fire_input)):
                    results[i].fire_smoke = boxes
            except Exception as exc:
                log.error("detection.fire.error", error=str(exc))

        # 4. Poz + düşme state machine
        if self._pose:
            try:
                for i, poses in enumerate(self._pose.detect_batch(frames)):
                    results[i].poses = self._pose.update_fall_states(poses)
            except Exception as exc:
                log.error("detection.pose.error", error=str(exc))

        # 5. Debug annotasyon (sadece LOG_LEVEL=DEBUG ise)
        if settings.log_level == "DEBUG" and _CV2_OK:
            for r in results:
                r.annotated_frame = annotate_frame(r)

        # Kamera başına en son sonucu sakla (snapshot/result endpoint'leri için)
        for r in results:
            self._latest_results[r.camera_id] = r

        self._frame_count += len(batch)
        self._batch_count += 1
        return results

    # ── Ana Döngü (async) ─────────────────────────────────────────────────────
    async def start(self, frame_queue: asyncio.Queue):
        self._running = True
        loop = asyncio.get_running_loop()

        log.info("detection.engine.start")

        # Modelleri arka plan thread'inde yükle (event loop'u bloklamaz)
        await loop.run_in_executor(_inference_pool, self._load_models)

        batch: List[Tuple[str, np.ndarray, float]] = []
        last_flush = time.time()
        batch_timeout = 0.1  # 100ms

        while self._running:
            # Kuyruktan frame al
            try:
                item = await asyncio.wait_for(frame_queue.get(), timeout=0.05)
                batch.append(item)
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                log.error("detection.frame_queue.error", error=str(exc))
                continue

            now = time.time()
            should_flush = (
                len(batch) >= settings.detection_batch_size
                or (batch and (now - last_flush) >= batch_timeout)
            )

            if should_flush and batch:
                to_process = batch.copy()
                batch.clear()
                last_flush = now

                # Inference'ı thread pool'da çalıştır
                det_results = await loop.run_in_executor(
                    _inference_pool, self._run_batch, to_process
                )

                # Sonuçları result_queue'ya koy
                for r in det_results:
                    try:
                        self.result_queue.put_nowait(r)
                    except asyncio.QueueFull:
                        # Kuyruğu boşaltmak yerine en eskiyi at, yeniyi koy
                        try:
                            self.result_queue.get_nowait()
                            self.result_queue.put_nowait(r)
                        except Exception:
                            pass

                # Periyodik metrik logu (her 60 sn)
                if (now - self._metrics_start) >= 60:
                    elapsed = now - self._metrics_start
                    fps = self._frame_count / elapsed if elapsed > 0 else 0.0
                    log.info(
                        "detection.engine.metrics",
                        avg_fps=round(fps, 1),
                        total_frames=self._frame_count,
                        total_batches=self._batch_count,
                        result_queue_size=self.result_queue.qsize(),
                    )
                    self._frame_count = 0
                    self._batch_count = 0
                    self._metrics_start = now

    def stop(self):
        self._running = False
        log.info("detection.engine.stop")

    # ── Durum Sorgulama ───────────────────────────────────────────────────────
    @property
    def is_ready(self) -> bool:
        return self._models_loaded

    def get_latest_result(self, camera_id: str) -> Optional[DetectionResult]:
        """Belirtilen kamera için en son işlenmiş DetectionResult'ı döndürür
        (henüz hiç frame işlenmediyse None)."""
        return self._latest_results.get(camera_id)

    def get_stats(self) -> dict:
        elapsed = time.time() - self._metrics_start
        return {
            "models_loaded": self._models_loaded,
            "models": model_registry.status(),
            "frame_count": self._frame_count,
            "batch_count": self._batch_count,
            "avg_fps": round(self._frame_count / max(elapsed, 1), 1),
            "result_queue_size": self.result_queue.qsize(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
detection_engine = DetectionEngine()


# ── Debug Annotation ──────────────────────────────────────────────────────────
_COLORS = {
    "person":    (0, 255, 0),
    "vehicle":   (255, 128, 0),
    "helmet":    (0, 200, 0),
    "no_hardhat": (0, 0, 255),
    "no_vest":   (0, 0, 255),
    "vest":      (0, 200, 0),
    "fire":      (0, 64, 255),
    "smoke":     (128, 128, 128),
}


def annotate_frame(result: DetectionResult) -> np.ndarray:
    """Debug: frame üzerine bounding box ve etiket çizer."""
    if not _CV2_OK:
        return result.frame
    frame = result.frame.copy()
    all_boxes = result.general + result.ppe + result.fire_smoke
    for b in all_boxes:
        color = _COLORS.get(b.class_name, (200, 200, 200))
        _cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), color, 2)
        label = f"{b.class_name} {b.confidence:.2f}"
        _cv2.putText(frame, label, (int(b.x1), int(b.y1) - 5),
                     _cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    # Düşme durumunu çiz
    for pose in result.poses:
        b = pose.bbox
        fall_color = (0, 0, 255) if pose.fall_state.value != "NORMAL" else (0, 255, 0)
        label = f"fall:{pose.fall_state.value} ({pose.body_angle:.0f}°)"
        _cv2.putText(frame, label, (int(b.x1), int(b.y2) + 15),
                     _cv2.FONT_HERSHEY_SIMPLEX, 0.45, fall_color, 1)
    return frame
