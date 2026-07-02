"""
Klip Üretimi — Faz 5 (Gün 16).

Olay tetiklendiğinde VideoBuffer'dan [olay - pre_buffer, olay + post_buffer]
aralığındaki JPEG frame'leri çekip MP4 klip yazar, klip path'ini event
kaydına işler ve WebSocket üzerinden CLIP_READY bildirimi yayınlar.

Yazma stratejisi:
1. FFmpeg (tercih edilen) — JPEG'ler stdin'den image2pipe ile beslenir,
   libx264 + yuv420p çıktı tarayıcıda doğrudan oynar (roadmap §5.7).
2. FFmpeg yoksa/başarısızsa cv2.VideoWriter (mp4v) fallback — tarayıcı
   uyumluluğu sınırlı ama klip yine de üretilir (VLC vb. oynatır).

Klip üretimi olay kaydını ASLA engellemez: tüm hatalar loglanıp yutulur,
klip üretilemezse event clip_path'siz kalır (degraded mod felsefesi).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
from typing import List, Optional, Set, Tuple

import cv2
import numpy as np
import structlog

from app.config import settings
from app.video.buffer import video_buffer_manager

log = structlog.get_logger()

# FFmpeg subprocess'in takılı kalmaması için üst sınır
_FFMPEG_TIMEOUT_SECONDS = 120
# Klip FPS'i frame zaman damgalarından hesaplanır; uç durumlara karşı kırpılır
_MIN_CLIP_FPS = 1.0
_MAX_CLIP_FPS = 30.0


def estimate_fps(timestamps: List[float]) -> float:
    """Frame zaman damgalarından gerçek FPS'i hesaplar (kırpılmış)."""
    if len(timestamps) < 2:
        return _MIN_CLIP_FPS
    span = timestamps[-1] - timestamps[0]
    if span <= 0:
        return _MIN_CLIP_FPS
    fps = (len(timestamps) - 1) / span
    return max(_MIN_CLIP_FPS, min(fps, _MAX_CLIP_FPS))


def _write_with_ffmpeg(frames: List[Tuple[bytes, float]], fps: float, path: str) -> bool:
    """JPEG frame'leri FFmpeg stdin'ine besleyerek H.264 MP4 yazar."""
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-loglevel", "error",
        "-f", "image2pipe",
        "-framerate", f"{fps:.3f}",
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",   # tarayıcı/oynatıcı uyumluluğu için şart
        "-crf", "23",
        "-movflags", "+faststart",
        path,
    ]
    proc = subprocess.run(
        cmd,
        input=b"".join(jpeg for jpeg, _ in frames),
        capture_output=True,
        timeout=_FFMPEG_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        log.warning(
            "clip.ffmpeg.failed",
            path=path,
            returncode=proc.returncode,
            stderr=proc.stderr.decode(errors="replace")[-500:],
        )
        return False
    return True


def _write_with_cv2(frames: List[Tuple[bytes, float]], fps: float, path: str) -> bool:
    """Fallback: JPEG'leri decode edip cv2.VideoWriter (mp4v) ile yazar."""
    first = cv2.imdecode(np.frombuffer(frames[0][0], dtype=np.uint8), cv2.IMREAD_COLOR)
    if first is None:
        return False
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(
        path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        return False
    try:
        for jpeg, _ in frames:
            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if frame.shape[:2] != (height, width):
                frame = cv2.resize(frame, (width, height))
            writer.write(frame)
    finally:
        writer.release()
    return True


def write_clip(
    event_id: str,
    frames: List[Tuple[bytes, float]],
    out_dir: Optional[str] = None,
) -> Optional[str]:
    """Frame listesinden MP4 klip yazar; başarıda path, hatada None döndürür.
    Senkron çalışır (subprocess + disk I/O) — executor'da çağrılmalıdır."""
    if len(frames) < 2:
        return None
    try:
        directory = out_dir or settings.clips_dir
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{event_id}.mp4")
        fps = estimate_fps([t for _, t in frames])

        try:
            ok = _write_with_ffmpeg(frames, fps, path)
        except FileNotFoundError:
            log.warning("clip.ffmpeg.not_found", binary=settings.ffmpeg_binary)
            ok = False
        except subprocess.TimeoutExpired:
            log.warning("clip.ffmpeg.timeout", event_id=event_id)
            ok = False

        if not ok:
            ok = _write_with_cv2(frames, fps, path)

        if not ok or not os.path.isfile(path):
            log.warning("clip.write_failed", event_id=event_id)
            return None
        return path
    except Exception as exc:
        log.warning("clip.error", event_id=event_id, error=str(exc))
        return None


class ClipService:
    """Olay başına klip üretimini arka planda yürütür.

    schedule() anında döner; asıl iş post-buffer süresi dolana kadar bekleyip
    buffer'dan frame'leri çeken, MP4 yazan ve DB'yi güncelleyen background
    task'te yapılır.
    """

    def __init__(self):
        # Task referansları tutulur — yoksa asyncio görevleri GC'ye kurban gider
        self._tasks: Set[asyncio.Task] = set()
        self._created_count = 0

    def schedule(self, event_id: str, camera_id: str, event_time: float):
        task = asyncio.create_task(
            self._create_clip(event_id, camera_id, event_time),
            name=f"clip-{event_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _create_clip(self, event_id: str, camera_id: str, event_time: float):
        try:
            # Post-buffer frame'lerinin buffer'a düşmesini bekle (+1 sn pay)
            wait = (event_time + settings.video_post_buffer_seconds + 1.0) - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

            frames = video_buffer_manager.get_frames(
                camera_id,
                event_time - settings.video_pre_buffer_seconds,
                event_time + settings.video_post_buffer_seconds,
            )
            if len(frames) < 2:
                log.warning(
                    "clip.no_frames",
                    event_id=event_id,
                    camera_id=camera_id,
                    frame_count=len(frames),
                )
                return

            loop = asyncio.get_running_loop()
            path = await loop.run_in_executor(None, write_clip, event_id, frames)
            if path is None:
                return

            await self._persist_clip_path(event_id, path)
            self._created_count += 1
            log.info(
                "clip.created",
                event_id=event_id,
                camera_id=camera_id,
                path=path,
                frames=len(frames),
            )

            # WebSocket'e klip hazır bildirimi (panel olay kartını güncelleyebilir)
            from app.alarm.manager import alarm_manager
            await alarm_manager.broadcast({
                "type": "CLIP_READY",
                "event_id": event_id,
                "camera_id": camera_id,
                "clip_url": f"/api/events/{event_id}/clip",
            })
        except Exception as exc:
            log.error("clip.task_error", event_id=event_id, error=str(exc))

    async def _persist_clip_path(self, event_id: str, path: str):
        """clip_path'i event kaydına yazar; DB hatası klip dosyasını geçersiz
        kılmaz, sadece loglanır."""
        # Import burada: db.crud → events.schemas zinciriyle döngüsel import'u önler
        from app.database import AsyncSessionLocal
        from app.db import crud
        try:
            async with AsyncSessionLocal() as db:
                await crud.set_event_clip_path(db, event_id, path)
        except Exception as exc:
            log.warning("clip.persist_failed", event_id=event_id, error=str(exc))

    def get_stats(self) -> dict:
        return {
            "created_clips": self._created_count,
            "pending_tasks": len(self._tasks),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
clip_service = ClipService()
