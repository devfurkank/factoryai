"""
Detection Engine — Faz 2 (Gün 4–8) kapsamında doldurulacak.
Şu an iskelet: kamera manager'ından gelen frame'leri kabul eder,
ileride YOLOv8 çıkarımı burada yapılacak.
"""
from __future__ import annotations
import asyncio
import structlog
from typing import List, Tuple
import numpy as np

log = structlog.get_logger()


class DetectionResult:
    def __init__(self, camera_id: str, timestamp: float, detections: list):
        self.camera_id = camera_id
        self.timestamp = timestamp
        self.detections = detections  # Faz 2'de doldurulacak


class DetectionEngine:
    """YOLOv8 batch inference motoru — Faz 2'de implement edilecek."""

    def __init__(self):
        self.result_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._running = False

    async def start(self, frame_queue: asyncio.Queue):
        self._running = True
        log.info("detection.engine.start", note="Faz 2'de YOLOv8 yüklenecek")
        while self._running:
            try:
                camera_id, frame, timestamp = await asyncio.wait_for(
                    frame_queue.get(), timeout=1.0
                )
                # TODO Faz 2: batch toplama + YOLO çıkarımı
                result = DetectionResult(camera_id, timestamp, [])
                await self.result_queue.put(result)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error("detection.engine.error", error=str(e))

    def stop(self):
        self._running = False


detection_engine = DetectionEngine()
