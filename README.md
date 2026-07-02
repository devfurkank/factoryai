# Fabrika Güvenlik Kameraları — Modüler AI Platformu

Gerçek zamanlı fabrika güvenlik kamera analizi: YOLOv8 tespit, ByteTrack takip, polygon zone ihlali, düşme/yangın/KKD tespiti, olay veritabanı ve web panel.

---

## Hızlı Başlangıç

```bash
# 1. Repo klonlandıktan sonra
cp .env.example .env
# .env'i düzenle (en az DB_PASSWORD ve APP_SECRET_KEY)

# 2. Tüm servisleri başlat
docker compose up -d --build

# 3. Sağlık kontrolü
curl http://localhost:8000/health
```

| Servis | URL |
|--------|-----|
| Backend API | http://localhost:8000 |
| API Dokümantasyon | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## Geliştirme Ortamı (Docker olmadan)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend (ayrı terminal)
cd frontend
npm install
npm run dev
```

### Webcam Testi (Faz 0)

```bash
python scripts/test_webcam.py
# Başka kamera cihazı için:
python scripts/test_webcam.py 1
```

---

## Proje Yapısı

```
.
├── backend/            FastAPI uygulaması
│   ├── app/
│   │   ├── camera/     Kamera yönetimi (RTSP + Webcam)
│   │   ├── detection/  YOLOv8 çıkarım motoru
│   │   ├── tracking/   ByteTrack nesne takibi
│   │   ├── rules/      Polygon zone, dwell time, mesafe
│   │   ├── events/     Olay motoru + risk puanlama
│   │   ├── video/      Video buffer + FFmpeg klip
│   │   ├── alarm/      WebSocket alarm yöneticisi
│   │   ├── llm/        Gemma özet + soru-cevap
│   │   ├── api/        FastAPI rotaları
│   │   └── db/         SQLAlchemy modelleri
│   └── tests/          Pytest test paketi
├── frontend/           React 18 + Vite + Tailwind
├── db/                 schema.sql (TimescaleDB)
├── docker/             Nginx + Prometheus konfigürasyonu
├── scripts/            Kurulum + test + demo scriptleri
├── docker-compose.yml
└── .env.example
```

---

## Kamera Yapılandırması

### Faz 0 — Laptop Webcam (varsayılan)

`.env` dosyasında:
```
WEBCAM_DEVICE_INDEX=0
```

`db/schema.sql` içinde `cam_laptop_01` kaydı otomatik eklenir.

### RTSP Kamera (Faz 1+)

Veritabanına RTSP kamera eklemek için `POST /api/cameras`:
```json
{
  "id": "cam_01",
  "name": "Depo Girişi",
  "source_type": "rtsp",
  "source_url": "rtsp://admin:pass@192.168.1.100:554/stream1",
  "location": "Depo — Giriş Kapısı"
}
```

---

## 30 Günlük Uygulama Fazları

| Faz | Günler | Durum |
|-----|--------|-------|
| **Faz 0** — Mimari Tasarım | 1 | ✅ Tamamlandı |
| Faz 1 — Altyapı | 2–3 | ✅ Tamamlandı |
| Faz 2 — Tespit (YOLOv8) | 4–8 | ✅ Tamamlandı |
| Faz 3 — Takip + Kural | 9–12 | ✅ Tamamlandı |
| Faz 4 — Olay Yönetimi | 13–15 | ✅ Tamamlandı |
| Faz 5 — Video + Alarm | 16–18 | ✅ Tamamlandı |
| Faz 6 — Raporlama | 19–23 | ⏳ Bekliyor |
| Faz 7 — Optimizasyon | 24–26 | ⏳ Bekliyor |
| Faz 8 — Entegrasyon | 27–28 | ⏳ Bekliyor |
| Faz 9 — Demo | 29–30 | ⏳ Bekliyor |

---

## Test

```bash
cd backend
pytest tests/ -v
```

Faz 0 testleri: `tests/test_camera.py`

---

## Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Backend | FastAPI 0.111, Python 3.11 |
| Frontend | React 18, Vite, Tailwind CSS |
| Veritabanı | PostgreSQL 16 + TimescaleDB |
| Mesaj Kuyruğu | Redis 7 (Streams) |
| AI/ML | YOLOv8 (Ultralytics), ByteTrack |
| Video | FFmpeg 6, OpenCV 4.9 |
| İzleme | Prometheus + Grafana |
| Container | Docker + Docker Compose |
