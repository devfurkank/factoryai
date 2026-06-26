import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import clsx from "clsx";

function CameraCard({ camera, status }) {
  const isOnline = status?.is_connected;
  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <div className="bg-black aspect-video flex items-center justify-center relative">
        <span className="text-slate-500 text-sm">HLS stream — Faz 5'te aktif</span>
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
