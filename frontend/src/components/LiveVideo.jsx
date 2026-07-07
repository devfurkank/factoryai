import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import Icon from "./Icon";

/**
 * Canlı video oynatıcı — Faz 5 mantığı + Faz 6 gecikme iyileştirmesi.
 *
 * İki mod:
 * - "mjpeg" (Anlık, VARSAYILAN): /api/detection/{id}/stream — tespit
 *   pipeline'ının en güncel frame'i (kutular + zone çizimleriyle), gecikme
 *   <1 sn. Webcam'in her zaman kullandığı yol; RTSP'de de en düşük gecikme
 *   bunu verir (HLS yapısal olarak segment × senkron kadar geride kalır).
 * - "hls" (Akıcı, sadece RTSP): FFmpeg HLS → hls.js. 1 sn segment +
 *   liveSyncDurationCount:1 ile ~2-3 sn gecikme; bant genişliği düşük,
 *   görüntü kaynağın orijinali (tespit çizimi yok).
 *
 * HLS oynatma fatal hata verirse otomatik MJPEG'e düşer.
 */
export default function LiveVideo({ camera, isOnline, mode = "mjpeg" }) {
  const videoRef = useRef(null);
  const [hlsFailed, setHlsFailed] = useState(false);

  // Kamera veya mod değişince önceki HLS hatasını unut
  useEffect(() => setHlsFailed(false), [camera.id, mode]);

  const useHls = mode === "hls" && camera.source_type === "rtsp" && !hlsFailed;

  useEffect(() => {
    if (!useHls || !videoRef.current) return;
    const src = `/streams/${camera.id}/stream.m3u8`;
    const video = videoRef.current;

    if (Hls.isSupported()) {
      const hls = new Hls({
        // Düşük gecikme ayarı: canlı uçtan 1 segment (≈1 sn) geriden oynat;
        // gecikme 5 segmenti aşarsa canlı uca atla, gerekirse %50 hızlandır.
        liveSyncDurationCount: 1,
        liveMaxLatencyDurationCount: 5,
        maxLiveSyncPlaybackRate: 1.5,
        backBufferLength: 10,
      });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          hls.destroy();
          setHlsFailed(true); // MJPEG fallback'e geç
        }
      });
      return () => hls.destroy();
    }
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src; // Safari native HLS
      return;
    }
    setHlsFailed(true);
  }, [useHls, camera.id]);

  if (!isOnline) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 text-on-surface-variant">
        <Icon name="videocam_off" className="text-2xl" />
        <span className="text-xs">Kamera bağlı değil</span>
      </div>
    );
  }

  if (useHls) {
    return (
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="w-full h-full object-contain"
      />
    );
  }

  return (
    <img
      src={`/api/detection/${camera.id}/stream`}
      alt={`${camera.name} canlı yayın`}
      className="w-full h-full object-contain"
    />
  );
}
