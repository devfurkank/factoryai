import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Cctv, MapPin, Activity, Zap, Film } from "lucide-react";
import { api } from "../api/client";
import { Card, Badge, EmptyState } from "../components/ui";
import LiveVideo from "../components/LiveVideo";

/** Görüntü kaynağı seçici — Anlık (MJPEG, <1 sn) / Akıcı (HLS, ~2-3 sn). */
function ModeToggle({ mode, onChange }) {
  const options = [
    { id: "mjpeg", label: "Anlık", icon: Zap, hint: "Tespit çizimli, en düşük gecikme (<1 sn)" },
    { id: "hls", label: "Akıcı", icon: Film, hint: "Orijinal görüntü, HLS (~2-3 sn gecikme)" },
  ];
  return (
    <div className="flex rounded-lg bg-slate-900/70 backdrop-blur p-0.5">
      {options.map(({ id, label, icon: Icon, hint }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          title={hint}
          className={clsx(
            "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition-colors",
            mode === id ? "bg-white text-slate-900" : "text-slate-300 hover:text-white"
          )}
        >
          <Icon className="w-3 h-3" />
          {label}
        </button>
      ))}
    </div>
  );
}

function CameraCard({ camera, status }) {
  const isOnline = status?.is_connected;
  // Varsayılan "mjpeg" (Anlık): HLS yapısal olarak segment süresi × senkron
  // kadar geride kalıyor — kullanıcı RTSP'de gecikmeyi kabul edilemez buldu.
  const [mode, setMode] = useState("mjpeg");
  const isRtsp = camera.source_type === "rtsp";

  return (
    <Card className="overflow-hidden group">
      <div className="bg-slate-900 aspect-video flex items-center justify-center relative">
        <LiveVideo camera={camera} isOnline={isOnline} mode={mode} />
        {/* Durum rozeti */}
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <span
            className={clsx(
              "flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-semibold backdrop-blur",
              isOnline ? "bg-emerald-500/90 text-white" : "bg-slate-700/90 text-slate-200"
            )}
          >
            <span className={clsx("w-1.5 h-1.5 rounded-full bg-white", isOnline && "animate-pulse")} />
            {isOnline ? "CANLI" : "ÇEVRİMDIŞI"}
          </span>
        </div>
        {/* Kaynak seçici — HLS yalnızca RTSP kameralarda mevcut */}
        {isRtsp && isOnline && (
          <div className="absolute top-3 right-3">
            <ModeToggle mode={mode} onChange={setMode} />
          </div>
        )}
      </div>
      <div className="p-4 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink truncate">{camera.name}</p>
          <p className="text-xs text-ink-faint mt-0.5 flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {camera.location || "Konum belirtilmemiş"}
          </p>
        </div>
        <Badge
          className={
            isOnline
              ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
              : "bg-slate-100 text-slate-500 ring-slate-200"
          }
        >
          <Activity className="w-3 h-3" />
          {isOnline ? `${status.fps.toFixed(1)} fps` : "—"}
        </Badge>
      </div>
    </Card>
  );
}

export default function LivePage() {
  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: api.cameras.list,
    refetchInterval: 10000,
  });
  const { data: statuses = [] } = useQuery({
    queryKey: ["cameras-status"],
    queryFn: api.cameras.allStatus,
    refetchInterval: 3000,
  });
  const statusMap = Object.fromEntries((statuses || []).map((s) => [s.camera_id, s]));
  const onlineCount = (statuses || []).filter((s) => s.is_connected).length;

  return (
    <div className="space-y-4 animate-fade-up">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-soft">
          <span className="font-semibold text-ink">{onlineCount}</span> / {cameras.length} kamera yayında
        </p>
        <p className="text-xs text-ink-faint">
          Anlık: tespit çizimli, &lt;1 sn gecikme · Akıcı: orijinal görüntü (HLS)
        </p>
      </div>

      {!isLoading && cameras.length === 0 ? (
        <Card>
          <EmptyState
            icon={Cctv}
            title="Kayıtlı kamera yok"
            hint="Kameralar sayfasından yeni kamera ekleyebilirsiniz."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <CameraCard key={cam.id} camera={cam} status={statusMap[cam.id]} />
          ))}
        </div>
      )}
    </div>
  );
}
