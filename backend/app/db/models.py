from sqlalchemy import (
    String, Integer, BigInteger, Float, Boolean, Text, JSON, Uuid,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP
from datetime import datetime
from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20), default="webcam")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_index: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    fps_limit: Mapped[int] = mapped_column(Integer, default=8)
    resolution: Mapped[str] = mapped_column(String(20), default="640x640")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    zone_type: Mapped[str] = mapped_column(String(50), default="forbidden")
    polygon: Mapped[dict] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    allowed_classes: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )


class Event(Base):
    __tablename__ = "events"
    # TimescaleDB hypertable: partition sütunu primary key'in parçası olmalı
    __table_args__ = (PrimaryKeyConstraint("id", "started_at"),)

    # DB'deki sütun UUID (bkz. migration 001). String(36) kullanılırsa SQLAlchemy
    # parametreyi ::VARCHAR cast'ler ve PostgreSQL "column id is of type uuid but
    # expression is of type character varying" hatası verir. Uuid(as_uuid=False)
    # ile Python tarafında str, SQL tarafında UUID olarak bağlanır.
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    camera_id: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    zone_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    track_ids: Mapped[list] = mapped_column(JSON, default=list)
    detected_classes: Mapped[list] = mapped_column(JSON, default=list)
    clip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_date: Mapped[str] = mapped_column(String(10))
    camera_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    high_risk_events: Mapped[int] = mapped_column(Integer, default=0)
    event_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )


class CameraHealth(Base):
    __tablename__ = "camera_health"
    # TimescaleDB hypertable: recorded_at primary key'in parçası olmalı
    __table_args__ = (PrimaryKeyConstraint("id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="online")
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
