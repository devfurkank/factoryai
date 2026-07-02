"""Rule Engine veri tipleri."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.events.schemas import EventType


@dataclass
class ZoneData:
    """DB'deki Zone satırının kural motoru için sadeleştirilmiş görünümü
    (SQLAlchemy oturumundan bağımsız — evaluator'lar bunu kullanır)."""

    id: str
    camera_id: str
    name: str
    zone_type: str
    polygon: List[List[float]]          # [[x, y], ...] — en az 3 nokta
    risk_level: str
    allowed_classes: List[str]
    rules: dict                         # örn. {"max_dwell_seconds": 10, "direction_line": [[x,y],[x,y]], "allowed_direction": "left_to_right"}
    is_active: bool = True


@dataclass
class RuleViolation:
    camera_id: str
    event_type: EventType
    track_ids: List[int]
    detected_classes: List[str]
    zone_id: Optional[str] = None
    risk_hint: dict = field(default_factory=dict)   # ek bağlam: mesafe, süre, yön...
    timestamp: float = field(default_factory=time.time)
