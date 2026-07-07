import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../../api/client";
import { useAlarms } from "../../context/AlarmContext";
import { Badge, EmptyState } from "../ui";
import Icon from "../Icon";
import ThemeToggle from "../ThemeToggle";
import { eventTypeLabel, SEVERITY_META, timeAgo } from "../../lib/format";

/** Zil + açılır canlı alarm listesi. */
function AlarmBell() {
  const { alarms, unread, markRead, connected } = useAlarms();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const toggle = () => {
    setOpen((o) => !o);
    if (!open) markRead();
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="relative text-on-surface-variant hover:text-primary transition-all p-2 rounded-full hover:bg-primary/5">
        <Icon name="notifications" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-error text-on-error text-[10px] font-bold flex items-center justify-center border border-surface">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 glass-panel-elevated rounded-xl shadow-pop z-50 animate-fade-up overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10">
            <p className="text-sm font-semibold text-on-surface">Canlı Alarmlar</p>
            <Badge className={connected ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : "bg-error/20 text-error border-error/30"}>
              {connected ? "Bağlı" : "Bağlantı yok"}
            </Badge>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {alarms.length === 0 ? (
              <EmptyState icon="notifications" title="Henüz alarm yok" hint="Yeni olaylar burada anlık görünür." />
            ) : (
              alarms.slice(0, 20).map((a, i) => {
                const sev = SEVERITY_META[a.severity] || SEVERITY_META.LOW;
                return (
                  <button
                    key={a.event_id || i}
                    onClick={() => {
                      setOpen(false);
                      navigate("/events");
                    }}
                    className="w-full flex items-start gap-3 px-4 py-3 hover:bg-primary/5 transition-colors text-left border-b border-outline-variant/20 last:border-0"
                  >
                    <span className={clsx("mt-1.5 w-2 h-2 rounded-full shrink-0", sev.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-on-surface truncate">
                        {eventTypeLabel(a.event_type)}
                      </p>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        {a.camera_id} · Risk {a.risk_score} · {timeAgo(a.timestamp)}
                      </p>
                    </div>
                    <Icon name="chevron_right" className="text-on-surface-variant shrink-0 mt-1 text-base" />
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Topbar() {
  const { connected } = useAlarms();
  const { data: health } = useQuery({
    queryKey: ["health"], queryFn: api.health, refetchInterval: 15000,
  });
  const healthy = health?.status === "ok";

  return (
    <header className="h-16 shrink-0 sticky top-0 z-30 glass-panel border-b border-primary/10 shadow-[0_0_20px_rgba(125,211,252,0.03)] flex items-center justify-between px-8">
      <div className="flex items-center gap-2 text-on-surface-variant text-sm">
        <span
          className={clsx(
            "w-2 h-2 rounded-full",
            healthy ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-error"
          )}
        />
        <span>
          {healthy ? "Sistem çalışıyor" : "Bağlantı sorunu"}
          {health ? ` · ${health.cameras} kamera · v${health.version}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-6">
        <span
          className={clsx(
            "font-semibold flex items-center gap-2 text-sm",
            connected ? "text-primary" : "text-on-surface-variant"
          )}
        >
          <Icon name="fiber_manual_record" className="text-sm" filled={connected} />
          {connected ? "Canlı bağlantı" : "Bağlantı kesildi"}
        </span>
        <div className="w-px h-6 bg-outline-variant/50" />
        <ThemeToggle />
        <AlarmBell />
        <div className="w-8 h-8 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-sm border border-primary/30">
          FK
        </div>
      </div>
    </header>
  );
}
