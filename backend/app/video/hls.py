"""
HLS Live Stream — Faz 5 (Gün 17).

Her aktif RTSP kamera için bir FFmpeg subprocess başlatır:
    rtsp://... → libx264 (ultrafast/zerolatency) → HLS segmentleri
    {streams_dir}/{camera_id}/stream.m3u8

Segmentler Docker'da nginx tarafından (/streams/ location), yerel geliştirmede
FastAPI StaticFiles mount'u ile servis edilir. Web panel hls.js ile oynatır.

Webcam kameralar BİLİNÇLİ olarak atlanır: FFmpeg'in işletim sistemine göre
farklı capture backend'i (dshow/v4l2/avfoundation) gerektirmesi ve cihazın
zaten CameraStream (OpenCV) tarafından açık olması nedeniyle — webcam canlı
izleme mevcut MJPEG endpoint'iyle yapılır (/api/detection/{id}/stream).

FFmpeg bulunamazsa veya HLS_ENABLED=false ise sistem HLS'siz çalışmaya devam
eder (degraded mod) — MJPEG akışı her kamera için her zaman kullanılabilir.

NOT — subprocess.Popen (asyncio.create_subprocess_exec DEĞİL) kullanılır:
Windows'ta `uvicorn --reload` event loop'u SelectorEventLoop'a zorlar ve bu
loop asyncio subprocess API'sini desteklemez (boş mesajlı NotImplementedError).
Popen event loop'tan bağımsızdır; poll() zaten non-blocking olduğu için
monitör döngüsünde async avantaj kaybı yoktur. FFmpeg stderr'i kamera başına
log dosyasına yazılır (streams/{id}/ffmpeg.log) — süreç ölünce kuyruğu loglanır.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Optional

import structlog

from app.camera.schemas import CameraConfig, SourceType
from app.config import settings

log = structlog.get_logger()

# Süreç çökmelerinde yeniden başlatma aralıkları (saniye)
_RESTART_BASE = 5
_RESTART_MAX = 60
# Monitör döngüsü kontrol sıklığı
_MONITOR_INTERVAL = 5
# Playlist bu süredir güncellenmediyse stream "stalled" sayılır
_STALL_THRESHOLD_SECONDS = 30


@dataclass
class HLSStream:
    camera_id: str
    source_url: str
    playlist_path: str
    process: Optional[subprocess.Popen] = None
    started_at: Optional[float] = None
    restart_count: int = 0
    restart_delay: int = _RESTART_BASE
    # Ölü sürecin yeniden başlatılacağı zaman (epoch) — monitör backoff'u
    # uyuyarak değil bu zaman damgasıyla bekler; böylece bir kameranın
    # backoff'u diğer kameraların izlenmesini/restart'ını geciktirmez.
    next_restart_at: Optional[float] = None
    last_error: Optional[str] = None

    @property
    def log_path(self) -> str:
        return os.path.join(os.path.dirname(self.playlist_path), "ffmpeg.log")

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def read_log_tail(self, max_bytes: int = 500) -> str:
        """FFmpeg stderr log dosyasının son kısmını okur (teşhis için)."""
        try:
            with open(self.log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                return f.read().decode(errors="replace").strip()
        except OSError:
            return ""

    @property
    def playlist_exists(self) -> bool:
        return os.path.isfile(self.playlist_path)

    @property
    def is_healthy(self) -> bool:
        """Süreç ayakta VE playlist yakın zamanda güncellenmiş mi?"""
        if not self.is_running or not self.playlist_exists:
            return False
        age = time.time() - os.path.getmtime(self.playlist_path)
        return age < _STALL_THRESHOLD_SECONDS


class HLSStreamManager:
    """RTSP kameraların HLS yayın süreçlerini yönetir (başlat/izle/yeniden başlat)."""

    def __init__(self):
        self._streams: Dict[str, HLSStream] = {}
        self._running = False
        self._ffmpeg_available: Optional[bool] = None
        self._monitor_task: Optional[asyncio.Task] = None

    # ── Kurulum ────────────────────────────────────────────────────────────────
    def _check_ffmpeg(self) -> bool:
        if self._ffmpeg_available is None:
            self._ffmpeg_available = shutil.which(settings.ffmpeg_binary) is not None
            if not self._ffmpeg_available:
                log.warning(
                    "hls.ffmpeg.not_found",
                    binary=settings.ffmpeg_binary,
                    note="HLS devre dışı — canlı izleme MJPEG üzerinden sürer",
                )
        return self._ffmpeg_available

    def _build_command(self, stream: HLSStream) -> list:
        segment_pattern = os.path.join(
            os.path.dirname(stream.playlist_path), "segment_%05d.ts"
        )
        return [
            settings.ffmpeg_binary,
            "-loglevel", "error",
            "-rtsp_transport", "tcp",       # UDP paket kaybına karşı (bkz. camera/stream.py)
            "-timeout", "8000000",          # RTSP socket I/O timeout (µs) — erişilemeyen
                                            # kaynakta süresiz takılmak yerine ~8sn'de öl
            # Düşük gecikme giriş ayarları: FFmpeg varsayılanı girişte ~5MB /
            # birkaç saniye buffer'lar (probe + demux) — canlı izlemede bu tek
            # başına 2-4 sn gecikme ekliyordu.
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "500000",         # 500KB — stream analizi için yeterli
            "-analyzeduration", "1000000",  # 1 sn
            # IP kamera/telefon kaynakları çoğunlukla düzgün FPS/timestamp
            # bildirmez; FFmpeg saçma bir kare hızı (90k tbr) algılayıp binlerce
            # kare kopyalıyor ve encoder hiç segment yazamıyordu ("MB rate >
            # level limit" + "More than 10000 frames duplicated" → stall).
            # Wallclock, kareye geliş zamanını damgalar — gerçek hız korunur.
            "-use_wallclock_as_timestamps", "1",
            "-i", stream.source_url,
            "-an",                           # ses yok — bant genişliği tasarrufu
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-r", str(settings.hls_fps),     # sabit çıkış FPS'i — kare kopyalama patlamasını önler
            "-g", str(settings.hls_fps * settings.hls_segment_seconds),  # segment başına 1 keyframe
            "-f", "hls",
            "-hls_time", str(settings.hls_segment_seconds),
            "-hls_list_size", str(settings.hls_list_size),
            # independent_segments: her segment kendi keyframe'iyle başlar —
            # oynatıcı canlı uca daha agresif atlayabilir (gecikme toparlama)
            "-hls_flags", "delete_segments+independent_segments",
            "-hls_segment_filename", segment_pattern,
            stream.playlist_path,
        ]

    # ── Yaşam Döngüsü ──────────────────────────────────────────────────────────
    async def start(self, camera_manager):
        """Aktif RTSP kameralar için HLS süreçlerini başlatır ve monitörü kurar."""
        if not settings.hls_enabled:
            log.info("hls.disabled_by_config")
            return
        if not self._check_ffmpeg():
            return

        self._running = True
        for config in camera_manager.list_cameras():
            if config.source_type == SourceType.rtsp and config.is_active:
                await self.add_camera(config)

        if not self._streams:
            log.info("hls.no_rtsp_cameras", note="HLS başlatılacak RTSP kamera yok")

        self._monitor_task = asyncio.create_task(self._monitor(), name="hls-monitor")

    async def add_camera(self, config: CameraConfig):
        """Tek bir RTSP kamera için HLS yayını başlatır (idempotent)."""
        if not self._running or config.source_type != SourceType.rtsp:
            return
        existing = self._streams.get(config.id)
        if existing and existing.is_running:
            return

        out_dir = os.path.join(settings.streams_dir, config.id)
        os.makedirs(out_dir, exist_ok=True)
        stream = HLSStream(
            camera_id=config.id,
            source_url=config.source_url or "",
            playlist_path=os.path.join(out_dir, "stream.m3u8"),
        )
        self._streams[config.id] = stream
        await self._spawn(stream)

    async def _spawn(self, stream: HLSStream):
        cmd = self._build_command(stream)
        try:
            # subprocess.Popen bilinçli tercih: asyncio.create_subprocess_exec,
            # Windows'ta uvicorn --reload'un zorladığı SelectorEventLoop'ta
            # NotImplementedError fırlatır (bkz. modül docstring'i).
            # Her spawn'da log dosyası sıfırdan açılır (taze teşhis).
            with open(stream.log_path, "wb") as log_file:
                stream.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=log_file,   # çocuk kendi descriptor kopyasını tutar
                )
            stream.started_at = time.time()
            stream.last_error = None
            log.info(
                "hls.stream.started",
                camera_id=stream.camera_id,
                playlist=stream.playlist_path,
                pid=stream.process.pid,
            )
        except Exception as exc:
            # repr(): NotImplementedError gibi boş mesajlı istisnalar str() ile
            # log'da görünmez oluyordu — tip adı her zaman görünür olmalı
            stream.last_error = repr(exc)
            log.error(
                "hls.stream.spawn_failed",
                camera_id=stream.camera_id,
                error=repr(exc),
            )

    async def _monitor(self):
        """Çöken/takılan FFmpeg süreçlerini backoff ile yeniden başlatır.

        Backoff beklemesi sleep ile DEĞİL, stream başına `next_restart_at`
        zaman damgasıyla yapılır — tek bir kameranın 60 sn'lik backoff'u
        diğer kameraların izlenmesini bloke etmemeli."""
        while self._running:
            await asyncio.sleep(_MONITOR_INTERVAL)
            now = time.time()
            for stream in list(self._streams.values()):
                if not self._running:
                    break
                if stream.is_running:
                    if stream.is_healthy:
                        stream.restart_delay = _RESTART_BASE  # sağlıklı → backoff sıfırla
                        continue
                    # Süreç ayakta ama playlist üretmiyor/güncellemiyor —
                    # ilk açılışa tolerans tanı, sonrasında "stalled" say ve
                    # süreci öldürüp normal yeniden başlatma yoluna sok.
                    age = now - (stream.started_at or 0)
                    if age < _STALL_THRESHOLD_SECONDS:
                        continue
                    log.warning(
                        "hls.stream.stalled",
                        camera_id=stream.camera_id,
                        age_seconds=round(age, 1),
                        playlist_exists=stream.playlist_exists,
                    )
                    await self._terminate(stream)

                # Süreç ölü — ilk fark edilişte teşhis + backoff planla
                if stream.next_restart_at is None:
                    if stream.process is not None:
                        tail = stream.read_log_tail()
                        if tail:
                            stream.last_error = tail
                    log.warning(
                        "hls.stream.died",
                        camera_id=stream.camera_id,
                        returncode=(
                            stream.process.poll() if stream.process is not None else None
                        ),
                        restart_in=stream.restart_delay,
                        error=stream.last_error,
                    )
                    stream.next_restart_at = now + stream.restart_delay
                    stream.restart_delay = min(stream.restart_delay * 2, _RESTART_MAX)
                    continue

                # Backoff süresi doldu mu?
                if now >= stream.next_restart_at:
                    stream.next_restart_at = None
                    stream.restart_count += 1
                    await self._spawn(stream)

    async def sync_camera(self, config: CameraConfig):
        """Çalışma anında eklenen/güncellenen/pasifleştirilen kamerayı HLS
        tarafına yansıtır (CameraManager._apply_camera_state çağırır).
        RTSP değilse veya pasifse mevcut yayını durdurur; URL değiştiyse
        yeniden başlatır; yoksa yeni yayın açar."""
        if not self._running:
            return
        stream = self._streams.get(config.id)

        if config.source_type != SourceType.rtsp or not config.is_active:
            if stream is not None:
                await self._terminate(stream)
                self._streams.pop(config.id, None)
                log.info("hls.stream.removed", camera_id=config.id)
            return

        if stream is not None:
            if stream.source_url == (config.source_url or "") and stream.is_running:
                return  # değişiklik yok
            await self._terminate(stream)
            self._streams.pop(config.id, None)
        await self.add_camera(config)

    async def restart(self, camera_id: str) -> bool:
        """Belirtilen kameranın HLS sürecini elle yeniden başlatır."""
        stream = self._streams.get(camera_id)
        if stream is None:
            return False
        await self._terminate(stream)
        stream.restart_count += 1
        stream.restart_delay = _RESTART_BASE
        stream.next_restart_at = None
        await self._spawn(stream)
        return True

    async def _terminate(self, stream: HLSStream):
        if stream.process is None or stream.process.poll() is not None:
            return
        loop = asyncio.get_running_loop()
        try:
            stream.process.terminate()
            # Popen.wait bloklayıcı — event loop'u dondurmamak için executor'da
            await loop.run_in_executor(None, stream.process.wait, 5)
        except subprocess.TimeoutExpired:
            stream.process.kill()
            await loop.run_in_executor(None, stream.process.wait)
        except Exception as exc:
            log.warning("hls.stream.terminate_failed",
                        camera_id=stream.camera_id, error=repr(exc))

    async def stop_all(self):
        self._running = False
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        for stream in self._streams.values():
            await self._terminate(stream)
        log.info("hls.all_stopped", count=len(self._streams))

    # ── Durum Sorgulama ────────────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return settings.hls_enabled and bool(self._ffmpeg_available)

    def get_status(self, camera_id: str) -> Optional[dict]:
        stream = self._streams.get(camera_id)
        if stream is None:
            return None
        return {
            "camera_id": stream.camera_id,
            "running": stream.is_running,
            "healthy": stream.is_healthy,
            "playlist_url": f"/streams/{stream.camera_id}/stream.m3u8",
            "playlist_exists": stream.playlist_exists,
            "started_at": stream.started_at,
            "restart_count": stream.restart_count,
            "last_error": stream.last_error,
        }

    def get_all_statuses(self) -> list:
        return [self.get_status(cid) for cid in self._streams]


# ── Singleton ─────────────────────────────────────────────────────────────────
hls_manager = HLSStreamManager()
