from pydantic import BaseModel, field_validator
from typing import Optional, Union
from enum import Enum


class SourceType(str, Enum):
    rtsp = "rtsp"
    webcam = "webcam"


class CameraProfile(BaseModel):
    models: list[str] = ["general"]
    rules: list[str] = ["zone"]
    detection_fps: int = 8


class CameraConfig(BaseModel):
    id: str
    name: str
    source_type: SourceType = SourceType.webcam
    # RTSP için URL, webcam için None
    source_url: Optional[str] = None
    # Webcam için cihaz indeksi (0 = ilk kamera)
    device_index: int = 0
    location: str = ""
    profile: CameraProfile = CameraProfile()
    fps_limit: int = 8
    resolution: str = "640x640"
    is_active: bool = True

    @field_validator("source_url")
    @classmethod
    def validate_rtsp_url(cls, v, info):
        source_type = info.data.get("source_type")
        if source_type == SourceType.rtsp and not v:
            raise ValueError("RTSP kaynağı için source_url gereklidir.")
        return v

    def get_capture_source(self) -> Union[str, int]:
        """OpenCV VideoCapture için kaynak döndürür."""
        if self.source_type == SourceType.webcam:
            return self.device_index
        return self.source_url  # type: ignore

    @property
    def display_name(self) -> str:
        if self.source_type == SourceType.webcam:
            return f"{self.name} (Webcam:{self.device_index})"
        return f"{self.name} ({self.source_url})"


class CameraStatus(BaseModel):
    camera_id: str
    is_connected: bool
    fps: float = 0.0
    last_frame_at: Optional[str] = None
    error: Optional[str] = None
