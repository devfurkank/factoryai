import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { Card, EmptyState } from "../components/ui";
import Icon from "../components/Icon";
import LiveVideo from "../components/LiveVideo";

/** Görüntü kaynağı seçici — Anlık (MJPEG, <1 sn) / Akıcı (HLS, ~2-3 sn). */
function ModeToggle({ mode, onChange }) {
  const options = [
    { id: "mjpeg", label: "Anlık", icon: "bolt", hint: "Tespit çizimli, en düşük gecikme (<1 sn)" },
    { id: "hls", label: "Akıcı", icon: "movie", hint: "Orijinal görüntü, HLS (~2-3 sn gecikme)" },
  ];
  return (
    <div className="flex rounded-lg bg-background/70 backdrop-blur p-0.5 border border-primary/10">
      {options.map(({ id, label, icon, hint }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          title={hint}
          className={clsx(
            "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition-colors",
            mode === id ? "bg-primary/90 text-on-primary" : "text-on-surface-variant hover:text-on-surface"
          )}
        >
          <Icon name={icon} className="text-[13px]" />
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
    <Card className={clsx("overflow-hidden flex flex-col relative group", !isOnline && "border-error/20")}>
      <div className="p-3 border-b border-primary/10 flex justify-between items-center bg-surface/40">
        <div className="flex items-center gap-2">
          <Icon name={isOnline ? "videocam" : "videocam_off"} className={clsx("text-[18px]", isOnline ? "text-on-surface-variant" : "text-error")} />
          <div>
            <h3 className="font-semibold text-sm text-on-surface">{camera.name}</h3>
            <p className="text-[10px] text-on-surface-variant uppercase tracking-wider">
              {camera.location || "Konum belirtilmemiş"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isRtsp && isOnline && <ModeToggle mode={mode} onChange={setMode} />}
          {isOnline ? (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-500/20 text-green-400 border border-green-500/30">
              CANLI
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-container-highest text-on-surface-variant border border-outline-variant">
              ÇEVRİMDIŞI
            </span>
          )}
        </div>
      </div>
      <div className="relative aspect-video bg-black/80 w-full overflow-hidden flex items-center justify-center">
        <LiveVideo camera={camera} isOnline={isOnline} mode={mode} />
        {isOnline && status?.fps != null && (
          <div className="absolute bottom-2 left-2 bg-black/50 backdrop-blur-sm text-on-surface text-[10px] px-2 py-1 rounded flex items-center gap-1 border border-white/10">
            <Icon name="speed" className="text-[12px]" />
            {status.fps.toFixed(1)} fps
          </div>
        )}
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
    <div className="space-y-8 animate-fade-up">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-headline font-bold text-on-surface mb-2 tracking-tight">Fabrika Zemin İzleme</h2>
          <p className="text-on-surface-variant text-sm">
            Gerçek zamanlı AI analizli kamera akışları ·{" "}
            <span className="font-semibold text-on-surface">{onlineCount}</span> / {cameras.length} kamera yayında
          </p>
        </div>
        <p className="text-xs text-on-surface-variant hidden md:block">
          Anlık: tespit çizimli, &lt;1 sn gecikme · Akıcı: orijinal görüntü (HLS)
        </p>
      </div>

      {!isLoading && cameras.length === 0 ? (
        <Card>
          <EmptyState
            icon="videocam"
            title="Kayıtlı kamera yok"
            hint="Kameralar sayfasından yeni kamera ekleyebilirsiniz."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {cameras.map((cam) => (
            <CameraCard key={cam.id} camera={cam} status={statusMap[cam.id]} />
          ))}
        </div>
      )}
    </div>
  );
}
