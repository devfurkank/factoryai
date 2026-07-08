"""Zone API Pydantic şemaları."""
from __future__ import annotations

import uuid
from typing import List

from pydantic import BaseModel, Field, field_validator


def _generate_zone_id() -> str:
    return f"zone_{uuid.uuid4().hex[:10]}"


class ZoneCreate(BaseModel):
    # id gönderilmezse otomatik üretilir (web panelindeki çizim aracı id üretmez)
    id: str = Field(default_factory=_generate_zone_id)
    camera_id: str
    name: str
    zone_type: str = "forbidden"
    # Noktalar normalize (0-1, çözünürlükten bağımsız — yeni çizim aracı) veya
    # piksel (eski kayıtlar) olabilir; ayrım için bkz. rules/geometry.py
    polygon: List[List[float]] = Field(..., min_length=3)
    risk_level: str = "medium"
    allowed_classes: List[str] = []
    rules: dict = {}
    is_active: bool = True

    @field_validator("polygon")
    @classmethod
    def _validate_points(cls, value: List[List[float]]) -> List[List[float]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("Her poligon noktası [x, y] çifti olmalı")
        return value


class ZoneResponse(ZoneCreate):
    pass
