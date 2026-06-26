-- Fabrika Güvenlik Kameraları — Veritabanı Şeması
-- PostgreSQL 16 + TimescaleDB

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Kamera Konfigürasyonu ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cameras (
    id          VARCHAR(50)  PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    source_type VARCHAR(20)  NOT NULL DEFAULT 'rtsp',  -- 'rtsp' | 'webcam'
    source_url  VARCHAR(500),          -- RTSP URL (source_type='rtsp' için)
    device_index INTEGER DEFAULT 0,    -- Webcam cihaz indeksi (source_type='webcam' için)
    location    VARCHAR(200),
    profile     JSONB        NOT NULL DEFAULT '{}',    -- model listesi, kural listesi
    fps_limit   INTEGER      NOT NULL DEFAULT 8,
    resolution  VARCHAR(20)  NOT NULL DEFAULT '640x640',
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Zone (Bölge) Tanımları ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zones (
    id              VARCHAR(100) PRIMARY KEY,
    camera_id       VARCHAR(50)  NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    zone_type       VARCHAR(50)  NOT NULL DEFAULT 'forbidden',  -- forbidden | monitoring | safe
    polygon         JSONB        NOT NULL,    -- [{"x": 100, "y": 200}, ...]
    risk_level      VARCHAR(20)  NOT NULL DEFAULT 'medium',     -- low | medium | high | critical
    allowed_classes JSONB        NOT NULL DEFAULT '[]',
    rules           JSONB        NOT NULL DEFAULT '{}',
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zones_camera ON zones(camera_id);

-- ── Olaylar (Events) — TimescaleDB hypertable ─────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id               UUID         NOT NULL DEFAULT gen_random_uuid(),
    camera_id        VARCHAR(50)  NOT NULL,
    event_type       VARCHAR(100) NOT NULL,   -- FORBIDDEN_ZONE_ENTRY | PPE_VIOLATION | FALL | FIRE | ...
    severity         VARCHAR(20)  NOT NULL,   -- LOW | MEDIUM | HIGH | CRITICAL
    risk_score       INTEGER      NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    started_at       TIMESTAMPTZ  NOT NULL,
    ended_at         TIMESTAMPTZ,
    zone_id          VARCHAR(100),
    track_ids        JSONB        NOT NULL DEFAULT '[]',
    detected_classes JSONB        NOT NULL DEFAULT '[]',
    clip_path        VARCHAR(500),
    thumbnail_path   VARCHAR(500),
    metadata         JSONB        NOT NULL DEFAULT '{}',
    status           VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | SUSTAINED | RESOLVED | ESCALATED
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, started_at)
);

-- TimescaleDB hypertable (zaman serisi partitioning)
SELECT create_hypertable('events', 'started_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_events_camera_time  ON events (camera_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_type_time    ON events (event_type, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_risk_time    ON events (risk_score DESC, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_status       ON events (status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_zone         ON events (zone_id, started_at DESC);

-- ── Günlük Özetler ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_summaries (
    id               SERIAL      PRIMARY KEY,
    summary_date     DATE        NOT NULL,
    camera_id        VARCHAR(50),             -- NULL → tüm kameralar
    total_events     INTEGER     NOT NULL DEFAULT 0,
    high_risk_events INTEGER     NOT NULL DEFAULT 0,
    event_breakdown  JSONB       NOT NULL DEFAULT '{}',
    summary_text     TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (summary_date, camera_id)
);

CREATE INDEX IF NOT EXISTS idx_summaries_date ON daily_summaries(summary_date DESC);

-- ── Kamera Sağlık Kayıtları ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS camera_health (
    id          BIGSERIAL   PRIMARY KEY,
    camera_id   VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'online',  -- online | offline | degraded
    fps         FLOAT,
    latency_ms  FLOAT,
    error_msg   TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('camera_health', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_health_camera ON camera_health(camera_id, recorded_at DESC);

-- ── Demo Veri: Varsayılan Kameralar ───────────────────────────────────────────
INSERT INTO cameras (id, name, source_type, device_index, location, profile, fps_limit)
VALUES
    (
        'cam_laptop_01',
        'Laptop Dahili Kamera',
        'webcam',
        0,
        'Geliştirme Ortamı — Laptop',
        '{"models": ["general", "pose"], "rules": ["zone", "dwell"], "detection_fps": 8}',
        8
    )
ON CONFLICT (id) DO NOTHING;
