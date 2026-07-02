"""
Thumbnail Üretimi — Faz 4 (Gün 14).

Olay anındaki frame'i tespit kutularıyla (annotate_frame) işaretler, üstüne
olay türü + kamera + zaman bandı ekler ve JPEG olarak thumbnails dizinine
yazar. Dosya adı event ID'sidir; dönen path event kaydına yazılır.

Senkron çalışır (cv2 encode + disk I/O) — EventEngine bunu run_in_executor
ile thread pool'da çağırır, event loop bloklanmaz.
"""
from __future__ import annotations

import os
from datetime import timezone
from typing import Optional

import cv2
import numpy as np
import structlog

from app.config import settings
from app.detection.engine import annotate_frame
from app.detection.types import DetectionResult
from app.events.schemas import EventCreate

log = structlog.get_logger()

_JPEG_QUALITY = 85
_BANNER_HEIGHT = 28
_BANNER_COLOR = (0, 0, 160)   # BGR — koyu kırmızı
_TEXT_COLOR = (255, 255, 255)


def render_thumbnail(result: DetectionResult, event: EventCreate) -> np.ndarray:
    """Frame'i annotate edip olay bilgisi bandı ekler (saf görüntü işleme —
    disk I/O yok, birim testlerde doğrudan çağrılabilir)."""
    frame = annotate_frame(result)

    ts = event.started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    label = f"{event.event_type.value} | {event.camera_id} | risk={event.risk_score} | {ts}"

    banner = np.zeros((_BANNER_HEIGHT, frame.shape[1], 3), dtype=frame.dtype)
    banner[:] = _BANNER_COLOR
    cv2.putText(banner, label, (8, _BANNER_HEIGHT - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _TEXT_COLOR, 1)
    return np.vstack([banner, frame])


def save_thumbnail(
    event_id: str,
    result: DetectionResult,
    event: EventCreate,
    out_dir: Optional[str] = None,
) -> Optional[str]:
    """Thumbnail'ı diske yazar; başarıda dosya path'ini, hatada None döndürür.
    Thumbnail üretilememesi olay kaydını engellememelidir — bu yüzden tüm
    hatalar loglanıp yutulur."""
    try:
        directory = out_dir or settings.thumbnails_dir
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{event_id}.jpg")

        image = render_thumbnail(result, event)
        ok = cv2.imwrite(path, image, [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY])
        if not ok:
            log.warning("event.thumbnail.write_failed", event_id=event_id, path=path)
            return None
        return path
    except Exception as exc:
        log.warning("event.thumbnail.error", event_id=event_id, error=str(exc))
        return None
