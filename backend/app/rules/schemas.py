"""Zone API Pydantic şemaları."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ZoneCreate(BaseModel):
    id: str
    camera_id: str
    name: str
    zone_type: str = "forbidden"
    polygon: List[List[float]] = Field(..., min_length=3)
    risk_level: str = "medium"
    allowed_classes: List[str] = []
    rules: dict = {}
    is_active: bool = True


class ZoneResponse(ZoneCreate):
    pass
