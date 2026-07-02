import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Hls from "hls.js";
import { api } from "../api/client";
import clsx from "clsx";

/**
 * Canlı video — Faz 5 (Gün 17).
 * RTSP kameralar: HLS (hls.js) → /streams/{id}/stream.m3u8 (FFmpeg + nginx).
 * Webcam kameralar veya HLS başarısızsa: MJPEG fallback
 * → /api/detection/{id}/stream (tespit kutuları + zone çizimleriyle).
 */
function LiveVideo({ camera, isOnline }) {
  const videoRef = useRef(null);
  const [hlsFailed, setHlsFailed] = useState(false);
  const useHls = camera.source_type === "rtsp" && !hlsFailed;

  useEffect(() => {
    if (!useHls || !videoRef.current) return;
    const src = `/streams/${camera.id}/stream.m3u8`;
    const video = videoRef.current;

    if (Hls.isSupported()) {
      const hls = new Hls({ liveSyncDurationCount: 2, maxLiveSyncPlaybackRate: 1.5 });
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
      <span className="text-slate-500 text-sm">Kamera bağlı değil</span>
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

function CameraCard({ camera, status }) {
  const isOnline = status?.is_connected;
  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="bg-black aspect-video flex items-center justify-center relative">
        <LiveVideo camera={camera} isOnline={isOnline} />
        <span
          className={clsx(
            "absolute top-2 right-2 w-2.5 h-2.5 rounded-full",
            isOnline ? "bg-ok" : "bg-danger"
          )}
        />
      </div>
      <div className="p-3">
        <p className="font-medium text-sm truncate">{camera.name}</p>
        <p className="text-xs text-slate-400 mt-0.5">
          {isOnline ? `${status.fps} fps` : "Bağlantı yok"} · {camera.location || "—"}
        </p>
      </div>
    </div>
  );
}

export default function CameraGrid() {
  const { data: cameras = [] } = useQuery({
    queryKey: ["cameras"],
    queryFn: api.cameras.list,
    refetchInterval: 5000,
  });

  const { data: statuses = [] } = useQuery({
    queryKey: ["cameras-status"],
    queryFn: api.cameras.allStatus,
    refetchInterval: 3000,
  });

  const statusMap = Object.fromEntries((statuses || []).map((s) => [s.camera_id, s]));

  if (!cameras.length) {
    return <p className="text-slate-500 text-sm p-4">Kayıtlı kamera yok.</p>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {cameras.map((cam) => (
        <CameraCard key={cam.id} camera={cam} status={statusMap[cam.id]} />
      ))}
    </div>
  );
}
