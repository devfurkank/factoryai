import asyncio
import time
import structlog
from typing import Dict, List, Optional
from app.camera.schemas import CameraConfig, CameraStatus
from app.camera.stream import CameraStream
from app.config import settings

log = structlog.get_logger()


class CameraManager:
    """
    Tüm kameraların yaşam döngüsünü yönetir.
    Her kamera için ayrı bir asyncio Task çalışır.
    """

    def __init__(self):
        self._cameras: Dict[str, CameraConfig] = {}
        self._streams: Dict[str, CameraStream] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        # frame_queue: downstream modüller bu kuyruğu dinler
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.frame_queue_size)

    # ── Kamera Kayıt ───────────────────────────────────────────────────────────
    def register(self, config: CameraConfig):
        self._cameras[config.id] = config
        log.info("camera.registered", camera_id=config.id, name=config.display_name)

    def register_all(self, configs: List[CameraConfig]):
        for cfg in configs:
            self.register(cfg)

    # ── Başlatma / Durdurma ────────────────────────────────────────────────────
    async def start_all(self):
        for camera_id, config in self._cameras.items():
            if config.is_active:
                await self._start_camera(camera_id)

    async def _start_camera(self, camera_id: str):
        config = self._cameras[camera_id]
        stream = CameraStream(
            config=config,
            frame_skip=settings.frame_skip,
            on_frame=self._on_frame,
        )
        self._streams[camera_id] = stream
        task = asyncio.create_task(stream.run(), name=f"stream-{camera_id}")
        self._tasks[camera_id] = task
        log.info("camera.started", camera_id=camera_id)

    async def stop_all(self):
        for camera_id, stream in self._streams.items():
            stream.stop()
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._streams.clear()
        log.info("camera.all_stopped")

    # ── Frame Callback ─────────────────────────────────────────────────────────
    async def _on_frame(self, camera_id: str, frame, timestamp: float):
        try:
            self.frame_queue.put_nowait((camera_id, frame, timestamp))
        except asyncio.QueueFull:
            # Kuyruğu taşırmak yerine eski frame'i at
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait((camera_id, frame, timestamp))
            except Exception:
                pass

    # ── Durum Sorgulama ────────────────────────────────────────────────────────
    def get_status(self, camera_id: str) -> Optional[CameraStatus]:
        stream = self._streams.get(camera_id)
        config = self._cameras.get(camera_id)
        if not config:
            return None
        return CameraStatus(
            camera_id=camera_id,
            is_connected=stream.is_connected if stream else False,
            fps=round(stream.fps, 1) if stream else 0.0,
            last_frame_at=(
                str(stream._last_frame_at) if stream and stream._last_frame_at else None
            ),
            error=stream.error if stream else None,
        )

    def get_all_statuses(self) -> List[CameraStatus]:
        return [self.get_status(cid) for cid in self._cameras if self.get_status(cid)]

    def list_cameras(self) -> List[CameraConfig]:
        return list(self._cameras.values())


# ── Singleton ──────────────────────────────────────────────────────────────────
camera_manager = CameraManager()


def get_default_cameras() -> List[CameraConfig]:
    """Faz 0: Laptop webcam'ini varsayılan kamera olarak döndürür.
    DISABLE_WEBCAM=true ise (Docker) kamera pasif kalır."""
    from app.camera.schemas import SourceType, CameraProfile
    return [
        CameraConfig(
            id="cam_laptop_01",
            name="Laptop Dahili Kamera",
            source_type=SourceType.webcam,
            device_index=settings.webcam_device_index,
            location="Geliştirme Ortamı",
            profile=CameraProfile(models=["general", "pose"], detection_fps=8),
            fps_limit=8,
            is_active=not settings.disable_webcam,
        )
    ]
