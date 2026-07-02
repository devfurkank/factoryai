"""
Faz 1 — Altyapı Testleri
- Redis client modülü
- DB CRUD modülü
- Health endpoint
- Kamera API (DB entegrasyonu)
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.camera.schemas import CameraConfig, SourceType, CameraProfile


# ── Redis Client ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_health_returns_bool():
    """check_redis_health bool döndürür (bağlanamasa False döner)."""
    from app.redis_client import check_redis_health
    result = await check_redis_health()
    assert isinstance(result, bool)


# ── DB CRUD ─────────────────────────────────────────────────────────────────


def test_row_to_config_roundtrip():
    """row_to_config: Camera satırını CameraConfig'e dönüştürür."""
    from app.db.models import Camera
    from app.db.crud import row_to_config
    from datetime import datetime

    row = Camera(
        id="cam_test",
        name="Test Kamera",
        source_type="webcam",
        source_url=None,
        device_index=0,
        location="Test",
        profile={"models": ["general"], "rules": ["zone"], "detection_fps": 8},
        fps_limit=8,
        resolution="640x640",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    config = row_to_config(row)
    assert config.id == "cam_test"
    assert config.source_type == SourceType.webcam
    assert config.fps_limit == 8
    assert isinstance(config.profile, CameraProfile)


@pytest.mark.asyncio
async def test_upsert_camera_updates_all_fields_on_existing_row():
    """upsert_camera: var olan bir satırı günceller derken is_active dışındaki
    alanları (name, location, fps_limit, profile, ...) da yazmalı — yalnızca
    is_active güncellenip diğerlerinin sessizce atlanması regresyon hatasıydı."""
    from app.database import AsyncSessionLocal
    from app.db.crud import upsert_camera, get_camera
    from app.camera.schemas import CameraConfig, SourceType, CameraProfile

    cam_id = "cam_test_upsert_regression"
    async with AsyncSessionLocal() as db:
        try:
            original = CameraConfig(
                id=cam_id, name="Once", source_type=SourceType.webcam,
                device_index=0, location="Depo A", fps_limit=8,
                profile=CameraProfile(models=["general"], detection_fps=8),
            )
            await upsert_camera(db, original)

            updated = CameraConfig(
                id=cam_id, name="Sonra", source_type=SourceType.webcam,
                device_index=1, location="Depo B", fps_limit=15,
                profile=CameraProfile(models=["general", "pose"], detection_fps=15),
            )
            await upsert_camera(db, updated)

            row = await get_camera(db, cam_id)
            assert row.name == "Sonra"
            assert row.device_index == 1
            assert row.location == "Depo B"
            assert row.fps_limit == 15
            assert row.profile.get("detection_fps") == 15
        finally:
            row = await get_camera(db, cam_id)
            if row is not None:
                await db.delete(row)
                await db.commit()


# ── API Health ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    """GET /health → 200 ve gerekli alanlar."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_cameras_endpoint_returns_list():
    """GET /api/cameras → liste döner (DB'de veri yoksa boş olabilir)."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/cameras")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_camera_status_endpoint():
    """GET /api/cameras/all/status → liste döner."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/cameras/all/status")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
