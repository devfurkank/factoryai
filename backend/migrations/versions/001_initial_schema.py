"""Initial schema — cameras, zones, events, daily_summaries, camera_health

Revision ID: 001
Revises:
Create Date: 2026-06-25

TimescaleDB extension + hypertable kurulumu dahil.
IF NOT EXISTS kullanıldığı için schema.sql ile çalışan Docker ortamında idempotent çalışır.
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy.sql import text

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    res = bind.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")).fetchone()
    has_timescale = res is not None

    if has_timescale:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id          VARCHAR(50)  PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            source_type VARCHAR(20)  NOT NULL DEFAULT 'webcam',
            source_url  VARCHAR(500),
            device_index INTEGER DEFAULT 0,
            location    VARCHAR(200),
            profile     JSONB        NOT NULL DEFAULT '{}',
            fps_limit   INTEGER      NOT NULL DEFAULT 8,
            resolution  VARCHAR(20)  NOT NULL DEFAULT '640x640',
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS zones (
            id              VARCHAR(100) PRIMARY KEY,
            camera_id       VARCHAR(50)  NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            name            VARCHAR(200) NOT NULL,
            zone_type       VARCHAR(50)  NOT NULL DEFAULT 'forbidden',
            polygon         JSONB        NOT NULL,
            risk_level      VARCHAR(20)  NOT NULL DEFAULT 'medium',
            allowed_classes JSONB        NOT NULL DEFAULT '[]',
            rules           JSONB        NOT NULL DEFAULT '{}',
            is_active       BOOLEAN      NOT NULL DEFAULT true,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_zones_camera ON zones(camera_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id               UUID         NOT NULL DEFAULT gen_random_uuid(),
            camera_id        VARCHAR(50)  NOT NULL,
            event_type       VARCHAR(100) NOT NULL,
            severity         VARCHAR(20)  NOT NULL,
            risk_score       INTEGER      NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
            started_at       TIMESTAMPTZ  NOT NULL,
            ended_at         TIMESTAMPTZ,
            zone_id          VARCHAR(100),
            track_ids        JSONB        NOT NULL DEFAULT '[]',
            detected_classes JSONB        NOT NULL DEFAULT '[]',
            clip_path        VARCHAR(500),
            thumbnail_path   VARCHAR(500),
            metadata         JSONB        NOT NULL DEFAULT '{}',
            status           VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, started_at)
        )
    """)
    if has_timescale:
        op.execute(
            "SELECT create_hypertable('events', 'started_at', if_not_exists => TRUE)"
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_camera_time ON events (camera_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_type_time   ON events (event_type, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_risk_time   ON events (risk_score DESC, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_status      ON events (status, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_zone        ON events (zone_id, started_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id               SERIAL      PRIMARY KEY,
            summary_date     DATE        NOT NULL,
            camera_id        VARCHAR(50),
            total_events     INTEGER     NOT NULL DEFAULT 0,
            high_risk_events INTEGER     NOT NULL DEFAULT 0,
            event_breakdown  JSONB       NOT NULL DEFAULT '{}',
            summary_text     TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (summary_date, camera_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_summaries_date ON daily_summaries(summary_date DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS camera_health (
            id          BIGSERIAL,
            camera_id   VARCHAR(50) NOT NULL,
            status      VARCHAR(20) NOT NULL DEFAULT 'online',
            fps         FLOAT,
            latency_ms  FLOAT,
            error_msg   TEXT,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, recorded_at)
        )
    """)
    if has_timescale:
        op.execute(
            "SELECT create_hypertable('camera_health', 'recorded_at', if_not_exists => TRUE)"
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_health_camera ON camera_health(camera_id, recorded_at DESC)")

    # Varsayılan kamera seed verisi
    op.execute("""
        INSERT INTO cameras (id, name, source_type, device_index, location, profile, fps_limit)
        VALUES (
            'cam_laptop_01',
            'Laptop Dahili Kamera',
            'webcam',
            0,
            'Geliştirme Ortamı — Laptop',
            '{"models": ["general", "pose"], "rules": ["zone", "dwell"], "detection_fps": 8}',
            8
        )
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS camera_health CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_summaries CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.execute("DROP TABLE IF EXISTS zones CASCADE")
    op.execute("DROP TABLE IF EXISTS cameras CASCADE")
