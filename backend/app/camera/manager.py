import asyncio
import os
import re
import time
from pathlib import Path
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
        # Kamera başına yalnızca EN GÜNCEL frame tutulur (FIFO kuyruk değil).
        # Neden: sabit boyutlu bir FIFO kuyruk (eski tasarım: maxsize=100)
        # işleme hızı üretim hızına yetişemediğinde geri dönüşü olmayan bir
        # birikim oluşturuyordu — istikrar durumunda dequeue edilen frame'in
        # yaşı tam olarak (kuyruk_boyutu / üretim_fps) kadar oluyordu
        # (100 kare / ~10fps ≈ 10 saniye gecikme — canlı izlemede fark edilir
        # hale geldi). En-güncel-frame modeli bu birikimi yapısal olarak
        # imkansız kılar: yeni frame her zaman öncekinin üzerine yazar,
        # işleme yetişemese bile gecikme büyümez, en fazla bir işleme
        # döngüsü kadar kalır.
        self._latest_frames: Dict[str, tuple] = {}  # camera_id -> (frame, timestamp)
        self.frame_ready = asyncio.Event()
        # start_all() çağrıldıktan sonra True olur; sonradan register() edilen
        # kameraların stream'inin otomatik başlatılması için kullanılır.
        self._started = False

    # ── Kamera Kayıt ───────────────────────────────────────────────────────────
    def register(self, config: CameraConfig):
        self._cameras[config.id] = config
        log.info("camera.registered", camera_id=config.id, name=config.display_name)
        # Manager zaten çalışıyorsa (uygulama açıldıktan sonra kamera eklendi/
        # güncellendiyse) stream'i hemen başlat/yeniden başlat.
        if self._started:
            asyncio.create_task(self._apply_camera_state(config.id))

    def register_all(self, configs: List[CameraConfig]):
        for cfg in configs:
            self.register(cfg)

    # ── Başlatma / Durdurma ────────────────────────────────────────────────────
    async def start_all(self):
        self._started = True
        for camera_id, config in self._cameras.items():
            if config.is_active:
                await self._start_camera(camera_id)

    async def _apply_camera_state(self, camera_id: str):
        """Çalışan bir manager'a kamera eklendiğinde/güncellendiğinde mevcut
        stream'i durdurup güncel config ile yeniden başlatır (veya pasifse durdurur)."""
        config = self._cameras.get(camera_id)
        if not config:
            return

        existing_stream = self._streams.pop(camera_id, None)
        existing_task = self._tasks.pop(camera_id, None)
        if existing_stream:
            existing_stream.stop()
        if existing_task:
            existing_task.cancel()
            try:
                await existing_task
            except asyncio.CancelledError:
                pass

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
        # Önceki (henüz işlenmemiş olsa bile) frame'in üzerine yazar —
        # bilinçli olarak: canlı izlemede geçmiş kareleri kovalamak yerine
        # her zaman en güncel kareyi işlemek tercih edilir.
        self._latest_frames[camera_id] = (frame, timestamp)
        self.frame_ready.set()

    def pop_latest_frames(self) -> List[tuple]:
        """O ana kadar biriken (kamera başına en fazla 1 tane) en güncel
        frame'leri döndürür ve bekleyen listeyi temizler. DetectionEngine
        tarafından her işleme döngüsünde çağrılır."""
        items = [(cid, frame, ts) for cid, (frame, ts) in self._latest_frames.items()]
        self._latest_frames.clear()
        self.frame_ready.clear()
        return items

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


_RTSP_ENV_PATTERN = re.compile(r"^RTSP_CAM_(\d+)$")
# backend/app/camera/manager.py -> backend/.env
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_candidate_env_values() -> Dict[str, str]:
    """RTSP_CAM_* gibi pydantic Settings'te tanımlı olmayan değişkenlere erişmek
    için `.env` dosyasını ayrıca okur. pydantic-settings, `.env` içeriğini
    yalnızca kendi modelinin alanlarına aktarır; `os.environ`'a yazmaz — bu
    yüzden tanımsız anahtarlar `os.environ` taramasıyla asla bulunamaz.
    Gerçek ortam değişkenleri (Docker -e, CI vb.) `.env` dosyasını ezer."""
    values: Dict[str, str] = {}
    if _ENV_FILE.exists():
        try:
            from dotenv import dotenv_values
            values.update({k: v for k, v in dotenv_values(_ENV_FILE).items() if v})
        except Exception as e:
            log.warning("camera.env_file.read_failed", path=str(_ENV_FILE), error=str(e))
    values.update(os.environ)
    return values


def get_rtsp_cameras_from_env() -> List[CameraConfig]:
    """`RTSP_CAM_<N>=rtsp://...` şeklindeki ortam değişkenlerinden RTSP kamera
    tanımları üretir. Opsiyonel: `RTSP_CAM_<N>_NAME`, `RTSP_CAM_<N>_LOCATION`."""
    from app.camera.schemas import SourceType, CameraProfile

    env_values = _load_candidate_env_values()
    cameras: List[CameraConfig] = []
    for key, value in sorted(env_values.items()):
        match = _RTSP_ENV_PATTERN.match(key)
        if not match or not value.strip():
            continue
        suffix = match.group(1)
        name = env_values.get(f"RTSP_CAM_{suffix}_NAME", f"RTSP Kamera {suffix}")
        location = env_values.get(f"RTSP_CAM_{suffix}_LOCATION", "")
        cameras.append(
            CameraConfig(
                id=f"cam_rtsp_{suffix}",
                name=name,
                source_type=SourceType.rtsp,
                source_url=value.strip(),
                location=location,
                profile=CameraProfile(models=["general", "pose"], detection_fps=8),
                fps_limit=8,
            )
        )
    return cameras


def get_default_cameras() -> List[CameraConfig]:
    """Faz 0: Laptop webcam'i + ortam değişkenleriyle tanımlanan RTSP kameraları
    döndürür. DISABLE_WEBCAM=true ise (Docker) webcam pasif kalır."""
    from app.camera.schemas import SourceType, CameraProfile
    cameras = [
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
    cameras.extend(get_rtsp_cameras_from_env())
    return cameras
