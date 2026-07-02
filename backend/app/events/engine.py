"""
Event Engine — Faz 4 (Gün 13).

Kural ihlallerinden (Faz 3 RuleEngine) ve tespit-bazlı alarmlardan (yangın,
düşme, KKD) olay üretir: risk puanlar, dedup uygular, thumbnail üretir ve
PostgreSQL'e yazar.

Akış (main.py::_detection_result_consumer):
    DetectionResult → tracking → rule_engine.evaluate() → RuleViolation[]
                   → event_engine.process(result, violations) → events DB

Dedup — Roadmap Gün 13: "aynı olay 5 saniye içinde tekrar üretilmez".
Kayan pencere kullanılır: bastırılan her tekrar pencereyi tazeler, böylece
sürekli devam eden bir durum (ör. yanan ateş her frame'de tespit edilir)
tek bir olay kaydı üretir; durum 5 sn boyunca hiç görülmezse bir sonraki
tespit YENİ bir olay olur.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import structlog

from app.config import settings
from app.detection.types import DetectionResult, FallState
from app.events.schemas import EventCreate, EventType
from app.events.scoring import compute_risk_score, severity_for_score
from app.events.thumbnails import save_thumbnail
from app.rules.types import RuleViolation

log = structlog.get_logger()

# Dedup anahtarı: (camera_id, event_type, zone_id, sıralı track_ids)
_DedupKey = Tuple[str, str, str, Tuple[int, ...]]


class EventEngine:
    """Kural ihlallerinden olay üretir, risk puanlar ve DB'ye yazar."""

    def __init__(self, dedup_seconds: Optional[float] = None):
        self._dedup_seconds = (
            dedup_seconds if dedup_seconds is not None else settings.event_dedup_seconds
        )
        self._last_seen: Dict[_DedupKey, float] = {}
        self._created_count = 0

    # ── Tespit-bazlı ihlal sentezi ────────────────────────────────────────────
    def detection_violations(self, result: DetectionResult) -> List[RuleViolation]:
        """Kural motorundan gelmeyen, doğrudan tespit çıktısına dayalı
        ihlalleri (yangın/duman, düşme, KKD) RuleViolation'a çevirir —
        böylece tek bir olay üretim yolundan geçerler."""
        violations: List[RuleViolation] = []

        # Yangın/duman — fire_detection.pt tek sınıflı olduğundan ayrım yok;
        # onaylı her tespit FIRE (maksimum risk) olarak ele alınır.
        if result.has_fire_or_smoke:
            violations.append(RuleViolation(
                camera_id=result.camera_id,
                event_type=EventType.FIRE,
                track_ids=[],
                detected_classes=["fire_smoke"],
                risk_hint={
                    "confidence": round(max(b.confidence for b in result.fire_smoke), 3),
                    "model_note": "tek sınıflı model — fire/smoke ayrımı yok",
                },
                timestamp=result.timestamp,
            ))

        # Düşme — pose state machine CONFIRMED/SUSTAINED durumları
        for pose in result.poses:
            if pose.fall_state not in (FallState.CONFIRMED, FallState.SUSTAINED):
                continue
            violations.append(RuleViolation(
                camera_id=result.camera_id,
                event_type=EventType.FALL,
                track_ids=[pose.track_id] if pose.track_id is not None else [],
                detected_classes=["person"],
                risk_hint={
                    "sustained": pose.fall_state == FallState.SUSTAINED,
                    "body_angle": round(pose.body_angle, 1),
                },
                timestamp=result.timestamp,
            ))

        # KKD ihlali — baretsiz kişi(ler)
        if result.has_ppe_violation:
            ppe_violations = [b for b in result.ppe if "no" in b.class_name.lower()]
            violations.append(RuleViolation(
                camera_id=result.camera_id,
                event_type=EventType.PPE_VIOLATION,
                track_ids=[],
                detected_classes=sorted({b.class_name for b in ppe_violations}),
                risk_hint={
                    "person_count": len(ppe_violations),
                    "confidence": round(max(b.confidence for b in ppe_violations), 3),
                },
                timestamp=result.timestamp,
            ))

        return violations

    # ── Olay üretimi (saf — DB'siz, birim test edilebilir) ────────────────────
    def build_events(self, violations: List[RuleViolation]) -> List[EventCreate]:
        """İhlal listesinden dedup + risk puanlama uygulayarak EventCreate
        listesi üretir."""
        events: List[EventCreate] = []

        for v in violations:
            key: _DedupKey = (
                v.camera_id,
                v.event_type.value,
                v.zone_id or "",
                tuple(sorted(v.track_ids)),
            )
            last = self._last_seen.get(key)
            self._last_seen[key] = v.timestamp  # kayan pencere: her görüşte tazele
            if last is not None and (v.timestamp - last) < self._dedup_seconds:
                continue

            risk_score = compute_risk_score(v.event_type, v.risk_hint)
            events.append(EventCreate(
                camera_id=v.camera_id,
                event_type=v.event_type,
                severity=severity_for_score(risk_score),
                risk_score=risk_score,
                started_at=datetime.fromtimestamp(v.timestamp, tz=timezone.utc),
                zone_id=v.zone_id,
                track_ids=list(v.track_ids),
                detected_classes=list(v.detected_classes),
                metadata=dict(v.risk_hint),
            ))

        self._prune_dedup_cache()
        return events

    def _prune_dedup_cache(self):
        """Penceresi çoktan dolmuş dedup kayıtlarını temizler (bellek sızıntısı
        önlemi — track ID'ler sürekli arttığı için anahtar uzayı büyüyebilir)."""
        if len(self._last_seen) < 1000:
            return
        cutoff = time.time() - self._dedup_seconds * 10
        self._last_seen = {k: t for k, t in self._last_seen.items() if t >= cutoff}

    # ── Uçtan uca işleme: ihlal → thumbnail → DB ─────────────────────────────
    async def process(
        self,
        result: Optional[DetectionResult],
        rule_violations: List[RuleViolation],
    ) -> List[str]:
        """Kural ihlalleri + tespit-bazlı ihlallerden olayları üretip DB'ye
        yazar; oluşturulan event ID'lerini döndürür. DB erişilemezse olaylar
        loglanır ama uygulama çalışmaya devam eder (degraded mod felsefesi)."""
        violations = list(rule_violations)
        if result is not None:
            violations += self.detection_violations(result)

        events = self.build_events(violations)
        if not events:
            return []

        loop = asyncio.get_running_loop()
        created_ids: List[str] = []

        # Import burada: db.crud → events.schemas zinciriyle döngüsel import'u önler
        from app.database import AsyncSessionLocal
        from app.db import crud

        for event in events:
            event_id = str(uuid.uuid4())

            thumbnail_path = None
            if result is not None and result.frame is not None:
                thumbnail_path = await loop.run_in_executor(
                    None, save_thumbnail, event_id, result, event
                )

            try:
                async with AsyncSessionLocal() as db:
                    await crud.create_event(
                        db, event, event_id=event_id, thumbnail_path=thumbnail_path
                    )
            except Exception as exc:
                log.error(
                    "event.persist_failed",
                    event_id=event_id,
                    event_type=event.event_type.value,
                    error=str(exc),
                )
                continue

            created_ids.append(event_id)
            self._created_count += 1
            log.warning(
                "event.created",
                event_id=event_id,
                camera_id=event.camera_id,
                event_type=event.event_type.value,
                severity=event.severity.value,
                risk_score=event.risk_score,
                zone_id=event.zone_id,
                track_ids=event.track_ids,
                thumbnail=thumbnail_path,
            )

        return created_ids

    def get_stats(self) -> dict:
        return {
            "created_events": self._created_count,
            "dedup_cache_size": len(self._last_seen),
            "dedup_window_seconds": self._dedup_seconds,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
event_engine = EventEngine()
