"""Rules API — Son üretilen kural ihlallerini gösterir (debug/doğrulama için).

Event Engine (Faz 4) henüz bu ihlalleri DB'ye yazmadığı için, RuleEngine
kamera başına son 50 ihlali bellekte tutar; bu endpoint o listeyi döndürür.
"""
from __future__ import annotations

from app.rules.engine import rule_engine
from fastapi import APIRouter

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("/{camera_id}/violations")
async def recent_violations(camera_id: str):
    violations = rule_engine.get_recent_violations(camera_id)
    return {
        "camera_id": camera_id,
        "count": len(violations),
        "violations": [
            {
                "event_type": v.event_type.value,
                "track_ids": v.track_ids,
                "detected_classes": v.detected_classes,
                "zone_id": v.zone_id,
                "risk_hint": v.risk_hint,
                "timestamp": v.timestamp,
            }
            for v in violations
        ],
    }
