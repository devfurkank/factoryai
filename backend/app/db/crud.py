from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Camera
from app.camera.schemas import CameraConfig, SourceType, CameraProfile


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
        cam.is_active = config.is_active
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
