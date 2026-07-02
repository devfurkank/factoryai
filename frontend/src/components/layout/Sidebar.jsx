import { NavLink } from "react-router-dom";
import clsx from "clsx";
import {
  LayoutDashboard,
  MonitorPlay,
  ShieldAlert,
  FileText,
  Sparkles,
  Cctv,
  Factory,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/live", label: "Canlı İzleme", icon: MonitorPlay },
  { to: "/events", label: "Olaylar", icon: ShieldAlert },
  { to: "/reports", label: "Raporlar", icon: FileText },
  { to: "/assistant", label: "AI Asistan", icon: Sparkles },
  { to: "/cameras", label: "Kameralar", icon: Cctv },
];

export default function Sidebar() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
  });
  const healthy = health?.status === "ok";

  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 bg-surface border-r border-line flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-16 border-b border-line">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm">
          <Factory className="w-5 h-5 text-white" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold tracking-tight text-ink">FabrikaAI</p>
          <p className="text-[11px] text-ink-faint">Güvenlik Platformu</p>
        </div>
      </div>

      {/* Navigasyon */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors",
                isActive
                  ? "bg-accent-soft text-accent-strong"
                  : "text-ink-soft hover:bg-slate-50 hover:text-ink"
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={clsx("w-[18px] h-[18px]", isActive ? "text-accent" : "text-ink-faint")} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Sistem durumu */}
      <div className="px-5 py-4 border-t border-line">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            {healthy && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
            )}
            <span
              className={clsx(
                "relative inline-flex rounded-full h-2.5 w-2.5",
                healthy ? "bg-emerald-500" : "bg-rose-500"
              )}
            />
          </span>
          <p className="text-xs font-medium text-ink-soft">
            {healthy ? "Sistem çalışıyor" : "Bağlantı sorunu"}
          </p>
        </div>
        <p className="text-[11px] text-ink-faint mt-1">
          {health ? `${health.cameras} kamera · v${health.version}` : "—"}
        </p>
      </div>
    </aside>
  );
}
