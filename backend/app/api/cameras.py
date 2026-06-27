from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.camera.manager import camera_manager
from app.camera.schemas import CameraConfig, CameraStatus
from app.database import get_db
from app.db import crud

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=List[CameraConfig])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    try:
        rows = await crud.list_cameras(db)
        # DB erişilebilir ve kayıt varsa döndür; yoksa bellek listesine geri dön
        if rows:
            return [crud.row_to_config(r) for r in rows]
    except Exception:
        pass
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
    except Exception:
        pass
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


@router.post("", response_model=CameraConfig, status_code=201)
async def add_camera(config: CameraConfig, db: AsyncSession = Depends(get_db)):
    try:
        await crud.upsert_camera(db, config)
    except Exception:
        pass
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
    except Exception:
        pass
    camera_manager.register(config)
    return config
