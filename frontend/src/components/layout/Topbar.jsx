import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Bell, Wifi, WifiOff, ChevronRight } from "lucide-react";
import { useAlarms } from "../../context/AlarmContext";
import { Badge, EmptyState } from "../ui";
import { eventTypeLabel, SEVERITY_META, timeAgo } from "../../lib/format";

const PAGE_TITLES = {
  "/": "Dashboard",
  "/live": "Canlı İzleme",
  "/events": "Olaylar",
  "/reports": "Raporlar",
  "/assistant": "AI Asistan",
  "/cameras": "Kameralar",
};

/** Zil + açılır canlı alarm listesi. */
function AlarmBell() {
  const { alarms, unread, markRead, connected } = useAlarms();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  // Dışarı tıklanınca kapat
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
      <button
        onClick={toggle}
        className={clsx(
          "relative p-2.5 rounded-xl transition-colors",
          open ? "bg-accent-soft text-accent" : "text-ink-soft hover:bg-slate-100"
        )}
      >
        <Bell className="w-[18px] h-[18px]" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 bg-surface border border-line rounded-2xl shadow-pop z-50 animate-fade-up overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-line">
            <p className="text-sm font-semibold text-ink">Canlı Alarmlar</p>
            <Badge
              className={
                connected
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : "bg-rose-50 text-rose-700 ring-rose-200"
              }
            >
              {connected ? "Bağlı" : "Bağlantı yok"}
            </Badge>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {alarms.length === 0 ? (
              <EmptyState icon={Bell} title="Henüz alarm yok" hint="Yeni olaylar burada anlık görünür." />
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
                    className="w-full flex items-start gap-3 px-4 py-3 hover:bg-slate-50 transition-colors text-left border-b border-line last:border-0"
                  >
                    <span className={clsx("mt-1.5 w-2 h-2 rounded-full shrink-0", sev.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-ink truncate">
                        {eventTypeLabel(a.event_type)}
                      </p>
                      <p className="text-xs text-ink-faint mt-0.5">
                        {a.camera_id} · Risk {a.risk_score} · {timeAgo(a.timestamp)}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-ink-faint shrink-0 mt-1" />
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
  const { pathname } = useLocation();
  const { connected } = useAlarms();
  const title = PAGE_TITLES[pathname] || "FabrikaAI";

  return (
    <header className="h-16 shrink-0 sticky top-0 z-40 bg-canvas/80 backdrop-blur border-b border-line flex items-center justify-between px-6">
      <div>
        <h1 className="text-lg font-bold tracking-tight text-ink">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <div
          className={clsx(
            "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium",
            connected ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
          )}
        >
          {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {connected ? "Canlı bağlantı" : "Bağlantı kesildi"}
        </div>
        <AlarmBell />
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center text-xs font-bold text-slate-600 ml-1">
          FK
        </div>
      </div>
    </header>
  );
}
