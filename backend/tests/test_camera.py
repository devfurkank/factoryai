"""Faz 0 — Başarı Kriteri Testi: Kamera ve yapılandırma doğrulama."""
import pytest
from app.camera.schemas import CameraConfig, SourceType
from app.camera.manager import get_default_cameras, get_rtsp_cameras_from_env, CameraManager
from app.config import settings


def test_default_cameras_returns_webcam():
    # NOT: get_default_cameras() yerel .env içindeki RTSP_CAM_* tanımlarını da
    # döndürebileceğinden toplam sayı yerine webcam kaydının varlığı doğrulanır.
    cameras = get_default_cameras()
    webcams = [c for c in cameras if c.source_type == SourceType.webcam]
    assert len(webcams) == 1
    cam = webcams[0]
    assert cam.id == "cam_laptop_01"
    assert cam.device_index == settings.webcam_device_index


def test_rtsp_cameras_from_env_parses_numbered_keys(monkeypatch):
    monkeypatch.setenv("RTSP_CAM_01", "rtsp://10.0.0.5:554/stream1")
    monkeypatch.setenv("RTSP_CAM_01_NAME", "Depo Kamerası")
    monkeypatch.setenv("RTSP_CAM_02", "rtsp://10.0.0.6:554/stream1")
    # Sayısal olmayan/eşleşmeyen anahtarlar yok sayılmalı
    monkeypatch.setenv("RTSP_CAM_02_LOCATION", "Sevkiyat")

    cameras = get_rtsp_cameras_from_env()

    by_id = {c.id: c for c in cameras}
    assert set(by_id) == {"cam_rtsp_01", "cam_rtsp_02"}
    assert by_id["cam_rtsp_01"].source_type == SourceType.rtsp
    assert by_id["cam_rtsp_01"].source_url == "rtsp://10.0.0.5:554/stream1"
    assert by_id["cam_rtsp_01"].name == "Depo Kamerası"
    assert by_id["cam_rtsp_02"].location == "Sevkiyat"


def test_webcam_capture_source_is_int():
    cam = CameraConfig(id="test", name="Test", source_type=SourceType.webcam, device_index=0)
    assert cam.get_capture_source() == 0


def test_rtsp_capture_source_is_str():
    cam = CameraConfig(
        id="rtsp_test",
        name="RTSP",
        source_type=SourceType.rtsp,
        source_url="rtsp://192.168.1.1:554/stream",
    )
    assert cam.get_capture_source() == "rtsp://192.168.1.1:554/stream"


def test_camera_manager_register():
    manager = CameraManager()
    cam = CameraConfig(id="cam_01", name="Cam 01", source_type=SourceType.webcam)
    manager.register(cam)
    assert len(manager.list_cameras()) == 1
    assert manager.list_cameras()[0].id == "cam_01"


def test_camera_status_not_connected_before_start():
    manager = CameraManager()
    cam = CameraConfig(id="cam_02", name="Cam 02", source_type=SourceType.webcam)
    manager.register(cam)
    status = manager.get_status("cam_02")
    assert status is not None
    assert status.is_connected is False
