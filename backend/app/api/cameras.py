from fastapi import APIRouter, HTTPException
from app.camera.manager import camera_manager
from app.camera.schemas import CameraConfig, CameraStatus
from typing import List

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=List[CameraConfig])
async def list_cameras():
    return camera_manager.list_cameras()


# Statik route'lar, {camera_id} param route'larından ÖNCE tanımlanmalı
@router.get("/all/status", response_model=List[CameraStatus])
async def all_camera_status():
    return camera_manager.get_all_statuses()


@router.get("/{camera_id}", response_model=CameraConfig)
async def get_camera(camera_id: str):
    cameras = {c.id: c for c in camera_manager.list_cameras()}
    if camera_id not in cameras:
        raise HTTPException(status_code=404, detail="Kamera bulunamadı")
    return cameras[camera_id]


@router.get("/{camera_id}/status", response_model=CameraStatus)
async def get_camera_status(camera_id: str):
    status = camera_manager.get_status(camera_id)
    if not status:
        raise HTTPException(status_code=404, detail="Kamera bulunamadı")
    return status


@router.post("", response_model=CameraConfig, status_code=201)
async def add_camera(config: CameraConfig):
    camera_manager.register(config)
    return config
