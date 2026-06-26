#!/usr/bin/env python3
"""
Faz 0 Başarı Kriteri — Laptop Webcam Testi
Çalıştır: python scripts/test_webcam.py
"""
import sys
import time
import cv2


def test_webcam(device_index: int = 0):
    print(f"=== Webcam Testi (cihaz indeksi: {device_index}) ===")
    cap = cv2.VideoCapture(device_index)

    if not cap.isOpened():
        print(f"[HATA] Kamera {device_index} açılamadı.")
        print("  → Başka bir uygulama kamerayı kullanıyor olabilir.")
        print("  → WEBCAM_DEVICE_INDEX değerini .env'de değiştirmeyi deneyin.")
        sys.exit(1)

    print(f"[OK] Kamera {device_index} açıldı.")

    frame_count = 0
    start = time.time()
    test_duration = 3  # saniye

    while (time.time() - start) < test_duration:
        ret, frame = cap.read()
        if not ret:
            print("[HATA] Frame okunamadı.")
            break
        frame_count += 1

    elapsed = time.time() - start
    fps = frame_count / elapsed if elapsed > 0 else 0

    cap.release()
    print(f"[OK] {frame_count} frame okundu — {fps:.1f} fps")
    print(f"[OK] Çözünürlük: {frame.shape[1]}x{frame.shape[0]}")
    print("[OK] Webcam testi başarılı.")


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    test_webcam(idx)
