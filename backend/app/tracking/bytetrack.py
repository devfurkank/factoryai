"""
ultralytics'in dahili BYTETracker'ı üzerine ince bir adaptör katmanı.

Neden kendi IOU tabanlı implementasyonumuz yerine bu: ultralytics paketi
zaten bir bağımlılığımız ve kendi BYTETracker/BoT-SORT implementasyonunu
içeriyor (saf Python + scipy/lapx ile Macar algoritması + Kalman filtresi).
Bunun tek eksik parçası olan `lapx` paketi hem Windows (win_amd64) hem
manylinux (Docker'ın python:3.11-slim tabanı) için önceden derlenmiş
wheel'lere sahip — yani cython_bbox'ın aksine hiçbir derleyici gerektirmeden
kurulabiliyor (bkz. requirements.txt notu). Bu adaptör, ultralytics'in
`results.conf/xywh/cls` bekleyen generic arayüzünü bizim BBox/TrackedObject
tiplerimize bağlıyor.

Davranış notu: ultralytics'in BYTETracker'ı yeni bir track'i yalnızca ilk
frame'de (frame_id == 1) anında "aktif" sayar; sonraki frame'lerde yeni bir
track bir sonraki eşleşmeye kadar `update()` çıktısında görünmez (iç
implementasyon detayı — bkz. ultralytics/trackers/byte_tracker.py). Bu
yüzden TrackedObject.state burada her zaman CONFIRMED'dir: aktive olmamış
track'ler zaten `update()` çıktısına hiç girmiyor.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, List

import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker as _UltralyticsByteTracker

from app.detection.types import BBox
from app.tracking.types import TrackedObject, TrackState


class _ClassCodec:
    """class_name (str) ↔ sayısal kod dönüşümü — ultralytics'in cls alanı
    numpy float array beklediği için gerekli."""

    def __init__(self):
        self._name_to_id: Dict[str, int] = {}
        self._id_to_name: Dict[int, str] = {}

    def encode(self, name: str) -> int:
        if name not in self._name_to_id:
            new_id = len(self._name_to_id)
            self._name_to_id[name] = new_id
            self._id_to_name[new_id] = name
        return self._name_to_id[name]

    def decode(self, code: int) -> str:
        return self._id_to_name.get(code, str(code))


def _to_results(detections: List[BBox], codec: _ClassCodec) -> SimpleNamespace:
    if not detections:
        return SimpleNamespace(
            xywh=np.zeros((0, 4), dtype=np.float32),
            conf=np.zeros((0,), dtype=np.float32),
            cls=np.zeros((0,), dtype=np.float32),
        )
    xywh = np.array(
        [
            (
                (d.x1 + d.x2) / 2,
                (d.y1 + d.y2) / 2,
                d.x2 - d.x1,
                d.y2 - d.y1,
            )
            for d in detections
        ],
        dtype=np.float32,
    )
    conf = np.array([d.confidence for d in detections], dtype=np.float32)
    cls = np.array([codec.encode(d.class_name) for d in detections], dtype=np.float32)
    return SimpleNamespace(xywh=xywh, conf=conf, cls=cls)


class ByteTracker:
    """
    Tek kamera için ultralytics BYTETracker sarmalayıcısı.
    Kamera başına ayrı örnek gerekir (bkz. TrackingEngine.trackers).
    """

    def __init__(
        self,
        high_thresh: float = 0.5,
        low_thresh: float = 0.1,
        new_thresh: float = 0.6,
        match_thresh: float = 0.8,
        max_age: int = 3,
    ):
        args = SimpleNamespace(
            track_high_thresh=high_thresh,
            track_low_thresh=low_thresh,
            new_track_thresh=new_thresh,
            track_buffer=max_age,
            match_thresh=match_thresh,
            fuse_score=True,
        )
        # frame_rate=30 + track_buffer=max_age → max_time_lost tam olarak
        # max_age frame'e eşit olur (bkz. BYTETracker.__init__ formülü:
        # max_time_lost = int(frame_rate / 30 * track_buffer)).
        self._tracker = _UltralyticsByteTracker(args, frame_rate=30)
        self._codec = _ClassCodec()

    def update(self, detections: List[BBox]) -> List[TrackedObject]:
        results = _to_results(detections, self._codec)
        rows = self._tracker.update(results)

        tracked: List[TrackedObject] = []
        for row in rows:
            x1, y1, x2, y2, track_id, score, _cls, idx = row
            det = detections[int(idx)]
            det.track_id = int(track_id)
            tracked.append(TrackedObject(
                track_id=int(track_id),
                class_name=det.class_name,
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(score),
                state=TrackState.CONFIRMED,
                hits=0,               # ultralytics bu bilgiyi dışa açmıyor
                time_since_update=0,  # update() çıktısı yalnızca bu frame'de eşleşenleri içerir
                first_seen=0.0,
                last_seen=0.0,
            ))
        return tracked

    def active_tracks(self) -> List[TrackedObject]:
        """Yeni frame beklemeden mevcut aktif track listesini döndürür (API/debug için)."""
        tracked: List[TrackedObject] = []
        for t in self._tracker.tracked_stracks:
            if not t.is_activated:
                continue
            x1, y1, x2, y2 = t.xyxy
            tracked.append(TrackedObject(
                track_id=t.track_id,
                class_name=self._codec.decode(int(t.cls)),
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(t.score),
                state=TrackState.CONFIRMED,
                hits=0,
                time_since_update=0,
                first_seen=0.0,
                last_seen=0.0,
            ))
        return tracked
