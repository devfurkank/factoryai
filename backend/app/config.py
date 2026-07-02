from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Uygulama
    app_env: str = "development"
    app_secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "factory_ai"
    postgres_user: str = "postgres"
    postgres_password: str = "PsQl41."
    database_url: str = "postgresql+asyncpg://postgres:PsQl41.@localhost:5432/factory_ai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kamera
    webcam_device_index: int = 0
    disable_webcam: bool = False

    # Modeller — Docker'da /app/models, yerel geliştirmede backend/models olarak ayarlayın
    models_dir: str = "/app/models"
    detection_confidence: float = 0.4
    detection_batch_size: int = 4
    yolo_general_model: str = "yolov8x.pt"
    yolo_pose_model: str = "yolov8m-pose.pt"
    yolo_ppe_model: str = "last_hardhat_200_epochs.pt"
    yolo_fire_model: str = "fire_detection.pt"

    # Frame işleme
    frame_skip: int = 3

    # Tracking — ultralytics BYTETracker adaptörü (bkz. app/tracking/bytetrack.py)
    track_high_thresh: float = 0.5    # 1. aşama (yüksek güvenli) eşleştirme alt sınırı
    track_low_thresh: float = 0.1     # 2. aşama (düşük güvenli) eşleştirme alt sınırı
    track_new_thresh: float = 0.6     # Yeni track açmak için minimum güven
    track_match_thresh: float = 0.8   # Eşleştirme kabul eşiği (ultralytics varsayılanı)
    track_max_age: int = 3            # Bu kadar frame üst üste eşleşmezse track silinir

    # Rule Engine
    distance_alert_pixels: float = 150.0  # Forklift (vehicle)-insan yakınlık eşiği (piksel)
    zones_cache_ttl_seconds: int = 30     # Zone tanımlarının DB'den yeniden okunma sıklığı

    # Video
    clips_dir: str = "/app/clips"
    thumbnails_dir: str = "/app/thumbnails"
    streams_dir: str = "/app/streams"
    video_pre_buffer_seconds: int = 10
    video_post_buffer_seconds: int = 10

    # Alarm
    alarm_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # LLM
    gemma_model: str = "google/gemma-2b-it"
    gemma_device: str = "cpu"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
