import { useEffect, useState } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import clsx from "clsx";

const SEVERITY_COLOR = {
  CRITICAL: "border-red-600 bg-red-950/40",
  HIGH: "border-orange-500 bg-orange-950/30",
  MEDIUM: "border-yellow-500 bg-yellow-950/20",
  LOW: "border-slate-500 bg-slate-800/40",
};

const TOAST_COLOR = {
  CRITICAL: "bg-red-700 border-red-500",
  HIGH: "bg-orange-700 border-orange-500",
  MEDIUM: "bg-yellow-700 border-yellow-500",
  LOW: "bg-slate-700 border-slate-500",
};

/** Yeni alarm geldiğinde 5 saniyeliğine görünen toast — Faz 5 (Gün 18). */
function AlarmToast({ alarm, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 5000);
    return () => clearTimeout(t);
  }, [alarm, onDismiss]);

  if (!alarm) return null;
  return (
    <div
      className={clsx(
        "fixed top-4 right-4 z-50 border rounded-lg px-4 py-3 shadow-lg",
        "text-white text-sm animate-pulse cursor-pointer",
        TOAST_COLOR[alarm.severity] || TOAST_COLOR.LOW
      )}
      onClick={onDismiss}
    >
      <p className="font-bold">
        ⚠ {alarm.event_type?.replace(/_/g, " ")}
      </p>
      <p className="text-xs mt-0.5 opacity-90">
        {alarm.camera_id} · Risk {alarm.risk_score} · {alarm.severity}
      </p>
    </div>
  );
}

export default function AlarmPanel() {
  const { connected, lastMessage } = useWebSocket("/ws/alarms");
  const [alarms, setAlarms] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!lastMessage || lastMessage === "pong") return;
    if (lastMessage.type === "ALARM") {
      setAlarms((prev) => [lastMessage, ...prev].slice(0, 50));
      setToast(lastMessage);
    }
    // Klip hazır olduğunda ilgili alarma clip_url'i işle (Faz 5 Gün 16)
    if (lastMessage.type === "CLIP_READY") {
      setAlarms((prev) =>
        prev.map((a) =>
          a.event_id === lastMessage.event_id
            ? { ...a, clip_url: lastMessage.clip_url }
            : a
        )
      );
    }
  }, [lastMessage]);

  return (
    <aside className="w-80 flex flex-col h-full border-l border-border bg-surface">
      <AlarmToast alarm={toast} onDismiss={() => setToast(null)} />
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h2 className="font-semibold text-sm">Canlı Alarmlar</h2>
        <span
          className={clsx(
            "text-xs px-2 py-0.5 rounded-full",
            connected ? "bg-ok/20 text-ok" : "bg-danger/20 text-danger"
          )}
        >
          {connected ? "Bağlı" : "Bağlantı yok"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {alarms.length === 0 && (
          <p className="text-slate-500 text-xs text-center mt-8">
            Henüz alarm yok
          </p>
        )}
        {alarms.map((a, i) => (
          <div
            key={a.event_id || i}
            className={clsx("border rounded p-2 text-xs", SEVERITY_COLOR[a.severity] || SEVERITY_COLOR.LOW)}
          >
            <p className="font-semibold">{a.event_type?.replace(/_/g, " ")}</p>
            <p className="text-slate-300 mt-0.5">Kamera: {a.camera_id}</p>
            <p className="text-slate-400">Risk: {a.risk_score} · {a.severity}</p>
            {a.thumbnail && (
              <img
                src={a.thumbnail}
                alt="olay görüntüsü"
                className="mt-1.5 rounded border border-border w-full"
                loading="lazy"
              />
            )}
            {a.clip_url && (
              <a
                href={a.clip_url}
                target="_blank"
                rel="noreferrer"
                className="inline-block mt-1.5 text-blue-400 hover:underline"
              >
                🎬 Video klip
              </a>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
