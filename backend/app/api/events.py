"""Events API — Faz 4 (Gün 15) + Faz 5 (Gün 16: /clip).

Olay listesi (filtreli + sayfalı), olay detayı, thumbnail, video klip,
günlük istatistik ve lifecycle durum güncellemesi.
"""
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.db import crud
from app.events.lifecycle import TERMINAL_STATUSES, InvalidTransition, validate_transition
from app.events.schemas import (
    EventListResponse,
    EventResponse,
    EventStatus,
    EventStatusUpdate,
    EventType,
    Severity,
)

router = APIRouter(prefix="/api/events", tags=["events"])


def _day_bounds(from_date: Optional[date], to_date: Optional[date]):
    """date filtrelerini [gün başı, gün sonu) UTC datetime aralığına çevirir."""
    from_time = (
        datetime.combine(from_date, time.min, tzinfo=timezone.utc) if from_date else None
    )
    to_time = (
        datetime.combine(to_date, time.min, tzinfo=timezone.utc) + timedelta(days=1)
        if to_date else None
    )
    return from_time, to_time


@router.get("", response_model=EventListResponse)
async def list_events(
    camera_id: Optional[str] = None,
    event_type: Optional[EventType] = None,
    severity: Optional[Severity] = None,
    status: Optional[EventStatus] = None,
    zone_id: Optional[str] = None,
    min_risk: Optional[int] = Query(default=None, ge=0, le=100),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Olay listesi — kamera, tür, önem, durum, bölge, risk ve tarih aralığına
    göre filtrelenebilir; started_at'e göre yeniden eskiye sıralıdır."""
    from_time, to_time = _day_bounds(from_date, to_date)
    rows, total = await crud.list_events(
        db,
        camera_id=camera_id,
        event_type=event_type.value if event_type else None,
        severity=severity.value if severity else None,
        status=status.value if status else None,
        zone_id=zone_id,
        min_risk=min_risk,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(
        items=[crud.event_row_to_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# Statik route'lar {event_id} param route'larından ÖNCE tanımlanmalı
@router.get("/stats/daily")
async def daily_stats(
    target_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """Günlük olay istatistikleri (UTC gün sınırlarına göre)."""
    return await crud.daily_event_stats(db, target_date or datetime.now(timezone.utc).date())


@router.get("/stats/hourly")
async def hourly_stats(
    target_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """Günün saatlik olay histogramı — dashboard grafiği (Faz 6)."""
    return await crud.hourly_event_stats(db, target_date or datetime.now(timezone.utc).date())


@router.get("/stats/range")
async def range_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Son N günün günlük olay sayıları — dashboard trend grafiği (Faz 6)."""
    return await crud.range_event_stats(db, days, datetime.now(timezone.utc).date())


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    row = await crud.get_event(db, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı")
    return crud.event_row_to_response(row)


@router.get("/{event_id}/thumbnail")
async def get_event_thumbnail(event_id: str, db: AsyncSession = Depends(get_db)):
    row = await crud.get_event(db, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı")
    if not row.thumbnail_path or not os.path.isfile(row.thumbnail_path):
        raise HTTPException(status_code=404, detail="Bu olay için thumbnail yok")
    return FileResponse(row.thumbnail_path, media_type="image/jpeg")


@router.get("/{event_id}/clip")
async def get_event_clip(event_id: str, db: AsyncSession = Depends(get_db)):
    """Olayın video klibini (pre/post buffer MP4) döndürür — Faz 5 (Gün 16).
    Klip, olay anından post-buffer süresi (varsayılan 10 sn) + işleme kadar
    sonra hazır olur; hazır değilse 404 döner."""
    row = await crud.get_event(db, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı")
    if not row.clip_path or not os.path.isfile(row.clip_path):
        raise HTTPException(
            status_code=404,
            detail="Bu olay için klip yok (henüz üretiliyor olabilir — "
                   "olay anından ~15 sn sonra tekrar deneyin)",
        )
    return FileResponse(
        row.clip_path,
        media_type="video/mp4",
        filename=f"{event_id}.mp4",
    )


@router.patch("/{event_id}/status", response_model=EventResponse)
async def update_event_status(
    event_id: str,
    payload: EventStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Olay lifecycle durumunu günceller (PENDING → ACTIVE → SUSTAINED →
    RESOLVED | ESCALATED). Geçersiz geçişler 400 döndürür; RESOLVED'a
    geçişte ended_at otomatik doldurulur."""
    row = await crud.get_event(db, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Olay bulunamadı")

    try:
        validate_transition(EventStatus(row.status), payload.status)
    except InvalidTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ended_at = (
        datetime.now(timezone.utc) if payload.status in TERMINAL_STATUSES else None
    )
    updated = await crud.update_event_status(
        db, event_id, payload.status.value, ended_at=ended_at
    )
    return crud.event_row_to_response(updated)
