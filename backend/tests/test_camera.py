"""Faz 0 — Başarı Kriteri Testi: Kamera ve yapılandırma doğrulama."""
import pytest
from app.camera.schemas import CameraConfig, SourceType
from app.camera.manager import get_default_cameras, CameraManager
from app.config import settings


def test_default_cameras_returns_webcam():
    cameras = get_default_cameras()
    assert len(cameras) == 1
    cam = cameras[0]
    assert cam.source_type == SourceType.webcam
    assert cam.device_index == settings.webcam_device_index


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
