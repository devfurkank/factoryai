import { useEffect, useState } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import clsx from "clsx";

const SEVERITY_COLOR = {
  CRITICAL: "border-red-600 bg-red-950/40",
  HIGH: "border-orange-500 bg-orange-950/30",
  MEDIUM: "border-yellow-500 bg-yellow-950/20",
  LOW: "border-slate-500 bg-slate-800/40",
};

export default function AlarmPanel() {
  const { connected, lastMessage } = useWebSocket("/ws/alarms");
  const [alarms, setAlarms] = useState([]);

  useEffect(() => {
    if (!lastMessage || lastMessage === "pong") return;
    if (lastMessage.type === "ALARM") {
      setAlarms((prev) => [lastMessage, ...prev].slice(0, 50));
    }
  }, [lastMessage]);

  return (
    <aside className="w-80 flex flex-col h-full border-l border-border bg-surface">
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
            key={i}
            className={clsx("border rounded p-2 text-xs", SEVERITY_COLOR[a.severity] || SEVERITY_COLOR.LOW)}
          >
            <p className="font-semibold">{a.event_type?.replace(/_/g, " ")}</p>
            <p className="text-slate-300 mt-0.5">Kamera: {a.camera_id}</p>
            <p className="text-slate-400">Risk: {a.risk_score} · {a.severity}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}
