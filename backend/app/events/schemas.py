from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class EventType(str, Enum):
    FORBIDDEN_ZONE_ENTRY = "FORBIDDEN_ZONE_ENTRY"
    PPE_VIOLATION = "PPE_VIOLATION"
    FALL = "FALL"
    INACTIVITY = "INACTIVITY"
    FIRE = "FIRE"
    SMOKE = "SMOKE"
    FORKLIFT_PROXIMITY = "FORKLIFT_PROXIMITY"
    DIRECTION_VIOLATION = "DIRECTION_VIOLATION"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSTAINED = "SUSTAINED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class EventCreate(BaseModel):
    camera_id: str
    event_type: EventType
    severity: Severity
    risk_score: int = Field(ge=0, le=100)
    started_at: datetime
    zone_id: Optional[str] = None
    track_ids: List[int] = []
    detected_classes: List[str] = []
    metadata: dict = {}


class EventResponse(BaseModel):
    id: str
    camera_id: str
    event_type: EventType
    severity: Severity
    risk_score: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    zone_id: Optional[str] = None
    track_ids: List[int] = []
    detected_classes: List[str] = []
    clip_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: dict = {}
    status: EventStatus
    created_at: datetime
