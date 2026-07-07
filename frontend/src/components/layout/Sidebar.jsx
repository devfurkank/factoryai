import { NavLink } from "react-router-dom";
import clsx from "clsx";
import Icon from "../Icon";

const NAV = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/live", label: "Canlı İzleme", icon: "live_tv" },
  { to: "/events", label: "Olaylar", icon: "notifications_active" },
  { to: "/reports", label: "Raporlar", icon: "assessment" },
  { to: "/assistant", label: "AI Asistan", icon: "smart_toy" },
  { to: "/cameras", label: "Kameralar", icon: "videocam" },
];

export default function Sidebar() {
  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 glass-panel border-r border-primary/10 shadow-[0_0_30px_rgba(125,211,252,0.05)] flex flex-col p-4 z-40">
      {/* Brand */}
      <div className="mb-8 px-2 mt-2 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl glass-panel-elevated flex items-center justify-center text-primary">
          <Icon name="security" filled />
        </div>
        <div>
          <h1 className="text-xl font-headline font-semibold tracking-tight text-primary">FabrikaAI</h1>
          <p className="text-xs text-on-surface-variant">Güvenlik Platformu</p>
        </div>
      </div>

      {/* Navigasyon */}
      <nav className="flex-1 space-y-2">
        {NAV.map(({ to, label, icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm tracking-wide transition-colors active:scale-95 duration-200",
                isActive
                  ? "text-primary bg-primary/10"
                  : "text-on-surface-variant hover:bg-primary/5 hover:text-primary"
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={icon} filled={isActive} />
                <span className={isActive ? "font-medium" : undefined}>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* CTA */}
      <div className="mt-auto pt-4 border-t border-outline-variant/30">
        <button className="w-full py-2.5 rounded-lg bg-primary/10 border border-primary/20 text-primary font-semibold hover:bg-primary/20 transition-colors flex items-center justify-center gap-2">
          <Icon name="analytics" className="text-sm" />
          <span>Sistem Analizi</span>
        </button>
      </div>
    </aside>
  );
}
