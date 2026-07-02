"""
Zone API — Poligon bölge tanımlarının CRUD işlemleri.
Her yazma işleminden sonra RuleEngine'in zone önbelleği hemen güncellenir
(30 saniyelik periyodik yenilemeyi beklemeden).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.db import crud
from app.db.models import Zone
from app.rules.engine import rule_engine
from app.rules.schemas import ZoneCreate, ZoneResponse

router = APIRouter(prefix="/api/zones", tags=["zones"])


def _row_to_response(row: Zone) -> ZoneResponse:
    return ZoneResponse(
        id=row.id,
        camera_id=row.camera_id,
        name=row.name,
        zone_type=row.zone_type,
        polygon=row.polygon if isinstance(row.polygon, list) else [],
        risk_level=row.risk_level,
        allowed_classes=row.allowed_classes or [],
        rules=row.rules or {},
        is_active=row.is_active,
    )


async def _refresh_rule_engine_cache(db: AsyncSession):
    rule_engine.set_zones(await crud.get_zones_by_camera(db))


@router.get("", response_model=List[ZoneResponse])
async def list_zones(camera_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    rows = (
        await crud.list_zones_for_camera(db, camera_id)
        if camera_id
        else await crud.list_zones(db)
    )
    return [_row_to_response(r) for r in rows]


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    row = await crud.get_zone(db, zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Zone bulunamadı")
    return _row_to_response(row)


@router.post("", response_model=ZoneResponse, status_code=201)
async def create_zone(zone: ZoneCreate, db: AsyncSession = Depends(get_db)):
    row = await crud.upsert_zone(db, zone)
    await _refresh_rule_engine_cache(db)
    return _row_to_response(row)


@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(zone_id: str, zone: ZoneCreate, db: AsyncSession = Depends(get_db)):
    if zone.id != zone_id:
        raise HTTPException(status_code=400, detail="URL ve body'deki zone ID'leri uyuşmuyor")
    row = await crud.upsert_zone(db, zone)
    await _refresh_rule_engine_cache(db)
    return _row_to_response(row)


@router.delete("/{zone_id}", status_code=204)
async def delete_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    ok = await crud.delete_zone(db, zone_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Zone bulunamadı")
    await _refresh_rule_engine_cache(db)
