"""
Video Buffer — Faz 5 (Gün 16).

Kamera başına pre/post olay ring buffer'ı. Frame'ler bellekte ham numpy dizisi
olarak DEĞİL, JPEG olarak tutulur: 1080p ham frame ~6MB iken JPEG'i ~100-200KB —
25 saniyelik buffer kamera başına ~0.5GB yerine ~20-40MB RAM tüketir. JPEG
encode maliyeti (~birkaç ms) thread pool'da ödenir, event loop bloklanmaz.

Akış:
    CameraManager._on_frame → video_buffer_manager.add_frame (encode executor'da)
                            → deque[(jpeg_bytes, timestamp)]
    Olay anında ClipService buffer'dan [olay-pre, olay+post] aralığını çekip
    MP4 yazar (bkz. app/video/clips.py).
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import structlog

from app.config import settings

log = structlog.get_logger()

# JPEG encode için ayrı, küçük thread pool — kamera okuma (cam-read) ve GPU
# inference (det-inf) havuzlarından bağımsız, onları yavaşlatmaz.
_encode_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vid-enc")


class VideoBuffer:
    """Tek kamera için JPEG ring buffer (pre + post + pay kadar saniye tutar)."""

    def __init__(
        self,
        camera_id: str,
        capacity_seconds: Optional[int] = None,
        nominal_fps: Optional[int] = None,
    ):
        self.camera_id = camera_id
        # Klip aralığının tamamı (+5 sn pay) buffer'da kalabilmeli
        self.capacity_seconds = capacity_seconds or (
            settings.video_pre_buffer_seconds + settings.video_post_buffer_seconds + 5
        )
        self.nominal_fps = nominal_fps or settings.video_buffer_max_fps
        self._frames: deque[Tuple[bytes, float]] = deque(
            maxlen=self.capacity_seconds * self.nominal_fps
        )

    def add_encoded(self, jpeg: bytes, timestamp: float):
        self._frames.append((jpeg, timestamp))

    def get_range(self, start_ts: float, end_ts: float) -> List[Tuple[bytes, float]]:
        """[start_ts, end_ts] aralığındaki frame'leri (kopya liste) döndürür."""
        return [(j, t) for j, t in self._frames if start_ts <= t <= end_ts]

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def span_seconds(self) -> float:
        if len(self._frames) < 2:
            return 0.0
        return self._frames[-1][1] - self._frames[0][1]


class VideoBufferManager:
    """Tüm kameraların video buffer'larını yönetir (kamera başına lazy oluşturma)."""

    def __init__(self):
        self._buffers: Dict[str, VideoBuffer] = {}

    def _get_buffer(self, camera_id: str) -> VideoBuffer:
        buf = self._buffers.get(camera_id)
        if buf is None:
            buf = VideoBuffer(camera_id)
            self._buffers[camera_id] = buf
            log.info(
                "video.buffer.created",
                camera_id=camera_id,
                capacity_seconds=buf.capacity_seconds,
                max_frames=buf._frames.maxlen,
            )
        return buf

    @staticmethod
    def _encode(frame: np.ndarray) -> Optional[bytes]:
        ok, jpeg = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), settings.clip_jpeg_quality]
        )
        return jpeg.tobytes() if ok else None

    async def add_frame(self, camera_id: str, frame: np.ndarray, timestamp: float):
        """Frame'i JPEG'e çevirip (thread pool'da) buffer'a ekler.

        Sıralama garantisi: CameraStream._read_loop on_frame'i kamera başına
        seri await ettiği için aynı kameranın frame'leri asla yer değiştirmez.
        """
        loop = asyncio.get_running_loop()
        jpeg = await loop.run_in_executor(_encode_pool, self._encode, frame)
        if jpeg is not None:
            self._get_buffer(camera_id).add_encoded(jpeg, timestamp)

    def add_frame_sync(self, camera_id: str, frame: np.ndarray, timestamp: float):
        """Senkron ekleme — testler ve thread içi kullanım için."""
        jpeg = self._encode(frame)
        if jpeg is not None:
            self._get_buffer(camera_id).add_encoded(jpeg, timestamp)

    def get_frames(
        self, camera_id: str, start_ts: float, end_ts: float
    ) -> List[Tuple[bytes, float]]:
        buf = self._buffers.get(camera_id)
        if buf is None:
            return []
        return buf.get_range(start_ts, end_ts)

    def get_stats(self) -> dict:
        now = time.time()
        return {
            camera_id: {
                "frames": buf.frame_count,
                "span_seconds": round(buf.span_seconds, 1),
                "newest_age_seconds": (
                    round(now - buf._frames[-1][1], 1) if buf.frame_count else None
                ),
            }
            for camera_id, buf in self._buffers.items()
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
video_buffer_manager = VideoBufferManager()
