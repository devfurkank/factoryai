"""
Poligon koordinat ölçekleme yardımcıları.

Web panelindeki çizim aracı zone poligonlarını video çözünürlüğünden bağımsız
olması için NORMALİZE (0-1 aralığı) koordinatlarla kaydeder. Kural motoru ve
canlı yayın çizimi ise piksel uzayında çalışır — bu modül ikisi arasındaki
dönüşümü yapar.

Sezgisel ayrım: tüm koordinatları [0, 1] aralığında olan bir nokta listesi
normalize kabul edilir (piksel uzayında 1×1 px içine sığan bir poligon
anlamsızdır); aksi halde eski kayıtlarla uyumluluk için piksel olarak
aynen kullanılır.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

# (height, width) — numpy frame.shape[:2] ile aynı sıra
FrameSize = Tuple[int, int]


def is_normalized(points: Sequence[Sequence[float]]) -> bool:
    """Tüm koordinatlar [0, 1] aralığındaysa True (normalize koordinat)."""
    try:
        return bool(points) and all(
            0.0 <= float(p[0]) <= 1.0 and 0.0 <= float(p[1]) <= 1.0 for p in points
        )
    except (TypeError, IndexError, ValueError):
        # Bozuk nokta verisi — piksel say, geçersizliği poligon kurulumu yakalar
        return False


def scale_points(
    points: Sequence[Sequence[float]],
    frame_size: Optional[FrameSize],
) -> List[List[float]]:
    """Normalize nokta listesini frame boyutuna (h, w) piksele ölçekler.

    Noktalar zaten piksel uzayındaysa veya frame_size bilinmiyorsa aynen
    (kopya olarak) döndürülür.
    """
    if frame_size is None or not is_normalized(points):
        return [list(p) for p in points]
    h, w = frame_size
    return [[float(p[0]) * w, float(p[1]) * h] for p in points]
