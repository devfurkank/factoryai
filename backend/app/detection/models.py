"""
Model Registry — YOLOv8 model yükleyici.
Tüm model ağırlıklarını merkezi olarak yönetir.
"""
from __future__ import annotations

import os
import structlog
from typing import Optional

log = structlog.get_logger()

try:
    from ultralytics import YOLO
    _ULTRALYTICS_OK = True
except ImportError:
    _ULTRALYTICS_OK = False
    log.error("detection.models.ultralytics_not_installed")


def _find_model_path(models_dir: str, filename: str) -> Optional[str]:
    """Model dosyasını birden fazla konumda arar."""
    candidates = [
        os.path.join(models_dir, filename),
        os.path.join("backend", "models", filename),
        os.path.join("models", filename),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", filename),
        filename,
    ]
    for path in candidates:
        normalized = os.path.normpath(path)
        if os.path.isfile(normalized):
            return normalized
    return None


class ModelRegistry:
    """
    Dört model türünü yükler ve sağlar:
    - general: person, araç tespiti (COCO)
    - pose:    YOLOv8-pose, düşme tespiti
    - ppe:     Baret/yelek ihlali
    - fire:    Yangın/duman tespiti
    """

    def __init__(self):
        self.general: Optional["YOLO"] = None
        self.pose: Optional["YOLO"] = None
        self.ppe: Optional["YOLO"] = None
        self.fire: Optional["YOLO"] = None
        self._loaded = False

    def load_all(
        self,
        models_dir: str,
        general_model: str,
        pose_model: str,
        ppe_model: str,
        fire_model: str,
    ):
        if not _ULTRALYTICS_OK:
            log.error("detection.models.cannot_load_ultralytics_missing")
            return

        self.general = self._load(models_dir, general_model, "general", allow_download=True)
        self.pose    = self._load(models_dir, pose_model,    "pose",    allow_download=True)
        self.ppe     = self._load(models_dir, ppe_model,     "ppe",     allow_download=False)
        self.fire    = self._load(models_dir, fire_model,    "fire",    allow_download=False)
        self._loaded = True

        log.info(
            "detection.models.all_loaded",
            general=general_model,
            pose=pose_model,
            ppe=ppe_model,
            fire=fire_model,
            loaded={
                "general": self.general is not None,
                "pose": self.pose is not None,
                "ppe": self.ppe is not None,
                "fire": self.fire is not None,
            },
        )

    def _load(
        self, models_dir: str, filename: str, name: str, allow_download: bool
    ) -> Optional["YOLO"]:
        path = _find_model_path(models_dir, filename)

        if path is None:
            if allow_download:
                # Ultralytics standard model: otomatik indirilir
                path = filename
                log.info("detection.model.auto_download", name=name, filename=filename)
            else:
                log.warning("detection.model.file_not_found", name=name, path=filename,
                            searched_in=models_dir)
                return None

        try:
            model = YOLO(path)
            classes = list(model.names.values()) if hasattr(model, "names") else []
            log.info("detection.model.loaded", name=name, path=path, classes=classes[:10])
            return model
        except Exception as exc:
            log.error("detection.model.load_failed", name=name, path=path, error=str(exc))
            return None

    @property
    def is_ready(self) -> bool:
        return self._loaded and self.general is not None

    def status(self) -> dict:
        return {
            "general": self.general is not None,
            "pose": self.pose is not None,
            "ppe": self.ppe is not None,
            "fire": self.fire is not None,
        }


model_registry = ModelRegistry()
