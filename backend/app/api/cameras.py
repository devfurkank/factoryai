import structlog
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.camera.manager import camera_manager
from app.camera.schemas import CameraConfig, CameraStatus
from app.database import get_db
from app.db import crud
from app.events.schemas import EventListResponse

log = structlog.get_logger()
router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=List[CameraConfig])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    try:
        rows = await crud.list_cameras(db)
        # DB erişilebilir ve kayıt varsa döndür; yoksa bellek listesine geri dön
        if rows:
            return [crud.row_to_config(r) for r in rows]
    except Exception as exc:
        log.warning("cameras.db_fallback", op="list", error=repr(exc))
    return camera_manager.list_cameras()


# Statik route {camera_id} param route'larından ÖNCE tanımlanmalı
@router.get("/all/status", response_model=List[CameraStatus])
async def all_camera_status():
    return camera_manager.get_all_statuses()


@router.get("/{camera_id}", response_model=CameraConfig)
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    try:
        row = await crud.get_camera(db, camera_id)
        if row:
            return crud.row_to_config(row)
    except Exception as exc:
        log.warning("cameras.db_fallback", op="get", error=repr(exc))
    # Bellek durumuna bak
    mem = {c.id: c for c in camera_manager.list_cameras()}
    if camera_id not in mem:
        raise HTTPException(status_code=404, detail="Kamera bulunamadı")
    return mem[camera_id]


@router.get("/{camera_id}/status", response_model=CameraStatus)
async def get_camera_status(camera_id: str):
    status = camera_manager.get_status(camera_id)
    if not status:
        raise HTTPException(status_code=404, detail="Kamera bulunamadı")
    return status


@router.get("/{camera_id}/events", response_model=EventListResponse)
async def get_camera_events(
    camera_id: str,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Kameranın olayları (Faz 4 — Gün 15), yeniden eskiye sıralı."""
    rows, total = await crud.list_events(db, camera_id=camera_id, limit=limit, offset=offset)
    return EventListResponse(
        items=[crud.event_row_to_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CameraConfig, status_code=201)
async def add_camera(config: CameraConfig, db: AsyncSession = Depends(get_db)):
    try:
        await crud.upsert_camera(db, config)
    except Exception as exc:
        log.warning("cameras.db_fallback", op="add", camera_id=config.id, error=repr(exc))
    camera_manager.register(config)
    return config


@router.put("/{camera_id}", response_model=CameraConfig)
async def update_camera(
    camera_id: str, config: CameraConfig, db: AsyncSession = Depends(get_db)
):
    if config.id != camera_id:
        raise HTTPException(status_code=400, detail="URL ve body'deki kamera ID'leri uyuşmuyor")
    try:
        await crud.upsert_camera(db, config)
    except Exception as exc:
        log.warning("cameras.db_fallback", op="update", camera_id=config.id, error=repr(exc))
    camera_manager.register(config)
    return config
