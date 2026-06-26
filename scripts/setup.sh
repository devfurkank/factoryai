#!/usr/bin/env bash
# ── Faz 0: İlk Kurulum Scripti ───────────────────────────────────────────────
set -euo pipefail

echo "=== Fabrika AI Platform — İlk Kurulum ==="

# .env oluştur (yoksa)
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] .env oluşturuldu (.env.example'dan kopyalandı)"
    echo "[!]  .env içindeki şifreleri değiştirmeyi unutmayın."
else
    echo "[--] .env zaten mevcut, atlanıyor."
fi

# Docker Compose servislerini başlat
echo ""
echo "=== Docker servisleri başlatılıyor... ==="
docker compose up -d --build

echo ""
echo "=== Servis durumu ==="
docker compose ps

echo ""
echo "=== Bağlantı Testi ==="
sleep 5
curl -s http://localhost:8000/health | python3 -m json.tool || echo "[WARN] Backend henüz hazır değil, biraz bekleyin."

echo ""
echo "=== Kurulum tamamlandı ==="
echo "  Backend API : http://localhost:8000"
echo "  Frontend    : http://localhost:3000"
echo "  Grafana     : http://localhost:3001  (admin/admin)"
echo "  Prometheus  : http://localhost:9090"
echo "  API Docs    : http://localhost:8000/docs"
