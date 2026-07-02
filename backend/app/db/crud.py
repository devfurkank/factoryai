from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Camera, Zone
from app.camera.schemas import CameraConfig, SourceType, CameraProfile
from app.rules.schemas import ZoneCreate
from app.rules.types import ZoneData


def _config_to_dict(config: CameraConfig) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "source_type": config.source_type.value,
        "source_url": config.source_url,
        "device_index": config.device_index,
        "location": config.location,
        "profile": config.profile.model_dump(),
        "fps_limit": config.fps_limit,
        "resolution": config.resolution,
        "is_active": config.is_active,
    }


def row_to_config(row: Camera) -> CameraConfig:
    profile_data = row.profile if isinstance(row.profile, dict) else {}
    return CameraConfig(
        id=row.id,
        name=row.name,
        source_type=SourceType(row.source_type),
        source_url=row.source_url,
        device_index=row.device_index or 0,
        location=row.location or "",
        profile=CameraProfile(**profile_data) if profile_data else CameraProfile(),
        fps_limit=row.fps_limit,
        resolution=row.resolution,
        is_active=row.is_active,
    )


async def upsert_camera(db: AsyncSession, config: CameraConfig) -> Camera:
    result = await db.execute(select(Camera).where(Camera.id == config.id))
    cam = result.scalar_one_or_none()
    data = _config_to_dict(config)
    if cam is None:
        cam = Camera(**data)
        db.add(cam)
    else:
        for key, value in data.items():
            if key != "id":
                setattr(cam, key, value)
        cam.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cam)
    return cam


async def list_cameras(db: AsyncSession) -> list[Camera]:
    result = await db.execute(
        select(Camera).where(Camera.is_active == True).order_by(Camera.created_at)
    )
    return list(result.scalars().all())


async def get_camera(db: AsyncSession, camera_id: str) -> Camera | None:
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    return result.scalar_one_or_none()


# ── Zone CRUD (Faz 3 — Rule Engine) ─────────────────────────────────────────────

def zone_row_to_data(row: Zone) -> ZoneData:
    return ZoneData(
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


async def list_zones(db: AsyncSession) -> list[Zone]:
    result = await db.execute(select(Zone).where(Zone.is_active == True).order_by(Zone.created_at))
    return list(result.scalars().all())


async def list_zones_for_camera(db: AsyncSession, camera_id: str) -> list[Zone]:
    result = await db.execute(
        select(Zone).where(Zone.camera_id == camera_id, Zone.is_active == True)
    )
    return list(result.scalars().all())


async def get_zone(db: AsyncSession, zone_id: str) -> Zone | None:
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    return result.scalar_one_or_none()


async def upsert_zone(db: AsyncSession, data: ZoneCreate) -> Zone:
    zone = await get_zone(db, data.id)
    payload = data.model_dump()
    if zone is None:
        zone = Zone(**payload)
        db.add(zone)
    else:
        for key, value in payload.items():
            if key != "id":
                setattr(zone, key, value)
    await db.commit()
    await db.refresh(zone)
    return zone


async def delete_zone(db: AsyncSession, zone_id: str) -> bool:
    zone = await get_zone(db, zone_id)
    if zone is None:
        return False
    await db.delete(zone)
    await db.commit()
    return True


async def get_zones_by_camera(db: AsyncSession) -> dict[str, list[ZoneData]]:
    """Tüm aktif zone'ları kamera ID'sine göre gruplayıp RuleEngine önbelleği
    için hazır ZoneData listesi döndürür."""
    rows = await list_zones(db)
    grouped: dict[str, list[ZoneData]] = {}
    for row in rows:
        grouped.setdefault(row.camera_id, []).append(zone_row_to_data(row))
    return grouped
