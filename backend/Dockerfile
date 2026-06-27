FROM python:3.11-slim

# Sistem bağımlılıkları (OpenCV + FFmpeg)
# Not: Debian Trixie'de libgl1-mesa-glx kaldırıldı, yerine libgl1 kullanılıyor
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gerekli dizinleri oluştur
RUN mkdir -p clips thumbnails streams models

EXPOSE 8000

# entrypoint.sh: alembic upgrade head → exec "$@"
ENTRYPOINT ["bash", "scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
