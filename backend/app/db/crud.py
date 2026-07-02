import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.models import Camera, Event, Zone
from app.camera.schemas import CameraConfig, SourceType, CameraProfile
from app.events.schemas import EventCreate, EventResponse
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


# ── Event CRUD (Faz 4 — Event Engine) ───────────────────────────────────────────

def event_row_to_response(row: Event) -> EventResponse:
    # id sütunu Docker/migration ortamında UUID, create_all ortamında VARCHAR —
    # her iki durumda da string'e normalize edilir.
    return EventResponse(
        id=str(row.id),
        camera_id=row.camera_id,
        event_type=row.event_type,
        severity=row.severity,
        risk_score=row.risk_score,
        started_at=row.started_at,
        ended_at=row.ended_at,
        zone_id=row.zone_id,
        track_ids=row.track_ids or [],
        detected_classes=row.detected_classes or [],
        clip_path=row.clip_path,
        thumbnail_path=row.thumbnail_path,
        metadata=row.metadata_ or {},
        status=row.status,
        created_at=row.created_at,
    )


async def create_event(
    db: AsyncSession,
    data: EventCreate,
    *,
    event_id: str,
    thumbnail_path: str | None = None,
) -> Event:
    row = Event(
        id=event_id,
        camera_id=data.camera_id,
        event_type=data.event_type.value,
        severity=data.severity.value,
        risk_score=data.risk_score,
        started_at=data.started_at,
        zone_id=data.zone_id,
        track_ids=data.track_ids,
        detected_classes=data.detected_classes,
        thumbnail_path=thumbnail_path,
        metadata_=data.metadata,
        status="ACTIVE",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def _event_filters(
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    zone_id: Optional[str] = None,
    min_risk: Optional[int] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
) -> list:
    conds = []
    if camera_id:
        conds.append(Event.camera_id == camera_id)
    if event_type:
        conds.append(Event.event_type == event_type)
    if severity:
        conds.append(Event.severity == severity)
    if status:
        conds.append(Event.status == status)
    if zone_id:
        conds.append(Event.zone_id == zone_id)
    if min_risk is not None:
        conds.append(Event.risk_score >= min_risk)
    if from_time is not None:
        conds.append(Event.started_at >= from_time)
    if to_time is not None:
        conds.append(Event.started_at < to_time)
    return conds


async def list_events(
    db: AsyncSession,
    *,
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    zone_id: Optional[str] = None,
    min_risk: Optional[int] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Event], int]:
    """Filtreli + sayfalı olay listesi; (satırlar, toplam) döndürür."""
    conds = _event_filters(
        camera_id, event_type, severity, status, zone_id, min_risk, from_time, to_time
    )
    total = await db.scalar(select(func.count()).select_from(Event).where(*conds)) or 0
    result = await db.execute(
        select(Event)
        .where(*conds)
        .order_by(Event.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get_event(db: AsyncSession, event_id: str) -> Event | None:
    # Sütun UUID tipli — geçersiz format driver seviyesinde hata (→ 500) üretir;
    # "bulunamadı" (None) olarak ele alınması doğru davranış.
    try:
        uuid.UUID(event_id)
    except (ValueError, AttributeError, TypeError):
        return None
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def set_event_clip_path(
    db: AsyncSession, event_id: str, clip_path: str
) -> Event | None:
    """Klip üretimi tamamlandığında (Faz 5 ClipService) clip_path'i yazar."""
    row = await get_event(db, event_id)
    if row is None:
        return None
    row.clip_path = clip_path
    await db.commit()
    await db.refresh(row)
    return row


async def update_event_status(
    db: AsyncSession,
    event_id: str,
    new_status: str,
    *,
    ended_at: Optional[datetime] = None,
) -> Event | None:
    row = await get_event(db, event_id)
    if row is None:
        return None
    row.status = new_status
    if ended_at is not None and row.ended_at is None:
        row.ended_at = ended_at
    await db.commit()
    await db.refresh(row)
    return row


async def daily_event_stats(db: AsyncSession, target_date: date) -> dict:
    """Belirtilen günün (UTC) olay istatistikleri: toplam, tür/önem/kamera
    kırılımı ve yüksek riskli (risk_score >= 70) olay sayısı."""
    day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    conds = [Event.started_at >= day_start, Event.started_at < day_end]

    total = await db.scalar(select(func.count()).select_from(Event).where(*conds)) or 0
    high_risk = await db.scalar(
        select(func.count()).select_from(Event).where(*conds, Event.risk_score >= 70)
    ) or 0

    async def _group_counts(column) -> dict:
        result = await db.execute(
            select(column, func.count()).where(*conds).group_by(column)
        )
        return {key: count for key, count in result.all()}

    return {
        "date": target_date.isoformat(),
        "total": int(total),
        "high_risk_events": int(high_risk),
        "by_type": await _group_counts(Event.event_type),
        "by_severity": await _group_counts(Event.severity),
        "by_camera": await _group_counts(Event.camera_id),
    }
