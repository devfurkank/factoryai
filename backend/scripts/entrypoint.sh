#!/bin/bash
# Fabrika AI Backend — Docker Entrypoint
# Alembic migrasyonlarını uygular (5 deneme), ardından uygulamayı başlatır.

set -e

echo "=== [Entrypoint] Alembic migration ==="
cd /app

MAX_RETRIES=5
RETRY_DELAY=5

for attempt in $(seq 1 $MAX_RETRIES); do
    if alembic upgrade head; then
        echo "=== [Entrypoint] Migration başarılı ==="
        break
    fi
    if [ "$attempt" -eq "$MAX_RETRIES" ]; then
        echo "[HATA] Migration $MAX_RETRIES denemede de başarısız oldu. Çıkılıyor."
        exit 1
    fi
    echo "[Retry $attempt/$MAX_RETRIES] Migration başarısız, ${RETRY_DELAY}s bekleniyor..."
    sleep $RETRY_DELAY
done

echo "=== [Entrypoint] Sunucu başlatılıyor: $@ ==="
exec "$@"
