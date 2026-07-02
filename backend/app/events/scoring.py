"""
Risk Puanlama — Faz 4 (Gün 13), Roadmap §5.5 risk matrisi.

| Olay Türü              | Baz Puan | Çarpan                             |
|------------------------|----------|-------------------------------------|
| Yasak bölge girişi     | 70       | Bölge risk seviyesi ×1.5 (high)     |
| KKD ihlali             | 60       | İnsan sayısı ×1.2 (birden fazla)    |
| Düşme                  | 95       | Süre >30s (SUSTAINED) ×1.3          |
| Hareketsizlik (dwell)  | 75       | Lokasyon kritikliği (zone risk)     |
| Duman tespiti          | 80       | Güven skoru ×1.4                    |
| Yangın tespiti         | 100      | — (maksimum)                        |
| Forklift-insan yakınlık| 65       | Mesafe çok yakınsa ×2.0             |
| Yön ihlali             | 50       | — (matris dışı, makul varsayılan)   |

Çarpan girdileri RuleViolation.risk_hint sözlüğünden gelir (Faz 3 evaluator'ları
bu bağlamı zaten dolduruyor: risk_level, dwell_seconds, distance_px, ...).
"""
from __future__ import annotations

from app.config import settings
from app.events.schemas import EventType, Severity

# Roadmap §5.5 baz puanları
BASE_SCORES: dict[EventType, int] = {
    EventType.FORBIDDEN_ZONE_ENTRY: 70,
    EventType.PPE_VIOLATION: 60,
    EventType.FALL: 95,
    EventType.INACTIVITY: 75,
    EventType.SMOKE: 80,
    EventType.FIRE: 100,
    EventType.FORKLIFT_PROXIMITY: 65,
    EventType.DIRECTION_VIOLATION: 50,
}

# Zone risk_level → çarpan (yasak bölge ve hareketsizlik için "lokasyon kritikliği")
_ZONE_RISK_MULTIPLIER = {"high": 1.5, "medium": 1.0, "low": 0.8}
_LOCATION_CRITICALITY = {"high": 1.2, "medium": 1.0, "low": 0.9}

# Duman: bu güvenin üzerindeki tespitler ×1.4 alır
_SMOKE_HIGH_CONFIDENCE = 0.7


def compute_risk_score(event_type: EventType, risk_hint: dict | None = None) -> int:
    """Olay türü + risk_hint bağlamından 0-100 arası risk puanı üretir."""
    hint = risk_hint or {}
    score = float(BASE_SCORES.get(event_type, 50))

    if event_type == EventType.FORBIDDEN_ZONE_ENTRY:
        score *= _ZONE_RISK_MULTIPLIER.get(hint.get("risk_level", "medium"), 1.0)

    elif event_type == EventType.PPE_VIOLATION:
        if int(hint.get("person_count", 1)) > 1:
            score *= 1.2

    elif event_type == EventType.FALL:
        if hint.get("sustained"):
            score *= 1.3

    elif event_type == EventType.INACTIVITY:
        score *= _LOCATION_CRITICALITY.get(hint.get("risk_level", "medium"), 1.0)

    elif event_type == EventType.SMOKE:
        if float(hint.get("confidence", 0.0)) >= _SMOKE_HIGH_CONFIDENCE:
            score *= 1.4

    elif event_type == EventType.FORKLIFT_PROXIMITY:
        # Roadmap "Mesafe <1m ×2.0" — piksel dünyasında alarm eşiğinin yarısından
        # yakın olmayı "çok yakın" sayıyoruz (gerçek dünya kalibrasyonu MVP dışı).
        distance = hint.get("distance_px")
        if distance is not None and float(distance) < settings.distance_alert_pixels / 2:
            score *= 2.0

    return max(0, min(100, int(round(score))))


def severity_for_score(score: int) -> Severity:
    if score >= 90:
        return Severity.CRITICAL
    if score >= 70:
        return Severity.HIGH
    if score >= 40:
        return Severity.MEDIUM
    return Severity.LOW
