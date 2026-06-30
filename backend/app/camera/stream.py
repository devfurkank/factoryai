import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
import cv2
import structlog
from typing import Callable, Awaitable
from app.camera.schemas import CameraConfig, SourceType

# cap.read() blocking çağrısı için ayrı thread pool
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cam-read")

log = structlog.get_logger()

# Yeniden bağlanma aralıkları (saniye)
_RECONNECT_BASE = 5
_RECONNECT_MAX = 60

# RTSP acma/okuma icin FFmpeg'in 30s varsayilani yerine kullanilan timeout (ms).
# Kamera erisilemezse hatayi hizli yakalayip yeniden baglanma dongusune erken
# girmek icin kisaltildi.
_RTSP_OPEN_TIMEOUT_MS = 8000
_RTSP_READ_TIMEOUT_MS = 8000


class CameraStream:
    """
    Tek kamera için RTSP veya Webcam okuma döngüsü.
    Her N. frame'i (frame_skip) frame_callback'e iletir.
    Bağlantı kopunca otomatik olarak yeniden bağlanır.
    """

    def __init__(
        self,
        config: CameraConfig,
        frame_skip: int = 3,
        on_frame: Callable[[str, object, float], Awaitable[None]] | None = None,
    ):
        self.config = config
        self.frame_skip = frame_skip
        self.on_frame = on_frame
        self._running = False
        self._frame_count = 0
        self._fps = 0.0
        self._last_frame_at: float | None = None
        self._error: str | None = None

    # ── Genel Durum ────────────────────────────────────────────────────────────
    @property
    def is_connected(self) -> bool:
        if self._last_frame_at is None:
            return False
        return (time.time() - self._last_frame_at) < 5.0  # 5s timeout

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def error(self) -> str | None:
        return self._error

    # ── Yardımcı ───────────────────────────────────────────────────────────────
    def _open_capture(self, source) -> cv2.VideoCapture:
        if self.config.source_type != SourceType.rtsp:
            return cv2.VideoCapture(source)

        # RTSP varsayilan olarak UDP transport dener; Docker bridge agi ve
        # NAT arkasindaki kameralarda UDP paketleri kayboluyor ve cap.read()
        # FFmpeg'in 30s ic timeout'una kadar sessizce takiliyor. TCP transport
        # zorlamak bu durumu buyuk olcude ortadan kaldirir.
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        return cv2.VideoCapture(
            source,
            cv2.CAP_FFMPEG,
            (
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, _RTSP_OPEN_TIMEOUT_MS,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, _RTSP_READ_TIMEOUT_MS,
            ),
        )

    # ── Ana Döngü ──────────────────────────────────────────────────────────────
    async def run(self):
        self._running = True
        reconnect_delay = _RECONNECT_BASE
        source = self.config.get_capture_source()

        log.info("camera.stream.start", camera_id=self.config.id, source=source)

        while self._running:
            cap = self._open_capture(source)

            if not cap.isOpened():
                self._error = f"Kaynak açılamadı: {source}"
                log.warning("camera.stream.open_failed",
                            camera_id=self.config.id, delay=reconnect_delay)
                cap.release()
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, _RECONNECT_MAX)
                continue

            self._error = None
            reconnect_delay = _RECONNECT_BASE
            # NOT: isOpened() RTSP/FFmpeg icin sadece handshake basarili oldugunda
            # True doner; ilk frame henuz okunmamis olabilir. Bu yuzden
            # "connected" eventi burada degil, _read_loop ilk frame'i basariyla
            # okuduktan sonra loglanir (bkz. _read_loop).
            log.debug("camera.stream.opened", camera_id=self.config.id)

            await self._read_loop(cap)
            cap.release()

            if self._running:
                log.warning("camera.stream.disconnected",
                            camera_id=self.config.id, reconnect_in=reconnect_delay)
                await asyncio.sleep(reconnect_delay)

    async def _read_loop(self, cap: cv2.VideoCapture):
        frame_idx = 0
        fps_counter = 0
        fps_window_start = time.time()
        loop = asyncio.get_running_loop()
        first_frame = True

        while self._running and cap.isOpened():
            # cap.read() bloklayıcı çağrısını thread pool'a taşı
            ret, frame = await loop.run_in_executor(_executor, cap.read)
            if not ret:
                self._error = "Frame okunamadı"
                break

            if first_frame:
                first_frame = False
                log.info("camera.stream.connected", camera_id=self.config.id)

            frame_idx += 1
            fps_counter += 1
            now = time.time()
            self._last_frame_at = now

            # FPS hesapla (her 30 frame'de bir güncelle)
            if fps_counter >= 30:
                elapsed = now - fps_window_start
                self._fps = fps_counter / elapsed if elapsed > 0 else 0.0
                fps_counter = 0
                fps_window_start = now

            # Frame atla
            if frame_idx % self.frame_skip != 0:
                continue

            self._frame_count += 1

            if self.on_frame:
                try:
                    await self.on_frame(self.config.id, frame, now)
                except Exception as e:
                    log.error("camera.stream.callback_error",
                              camera_id=self.config.id, error=str(e))

    def stop(self):
        self._running = False
        log.info("camera.stream.stop", camera_id=self.config.id)
