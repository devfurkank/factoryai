"""Video Buffer — Faz 5 (Gün 16) kapsamında implement edilecek."""
from collections import deque
import numpy as np
import structlog

log = structlog.get_logger()


class VideoBuffer:
    """Pre/post olay video arabelleği (ring buffer)."""

    def __init__(self, camera_id: str, pre_seconds: int = 10, fps: int = 15):
        self.camera_id = camera_id
        self.fps = fps
        self.buffer: deque = deque(maxlen=pre_seconds * fps)

    def add_frame(self, frame: np.ndarray, timestamp: float):
        self.buffer.append((frame.copy(), timestamp))

    def extract_clip(self, event_id: str, event_time: float) -> str:
        # TODO Faz 5: Pre buffer + post buffer → FFmpeg MP4 üretimi
        return f"/clips/{event_id}.mp4"
