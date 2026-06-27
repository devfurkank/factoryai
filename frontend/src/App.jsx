import { useState } from "react";
import CameraGrid from "./components/CameraGrid";
import AlarmPanel from "./components/AlarmPanel";
import Dashboard from "./components/Dashboard";
import clsx from "clsx";

const TABS = [
  { id: "live", label: "Canlı İzleme" },
  { id: "dashboard", label: "Dashboard" },
  { id: "events", label: "Olaylar" },
];

export default function App() {
  const [tab, setTab] = useState("live");

  return (
    <div className="flex flex-col h-screen bg-[#0f172a] text-slate-100">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="flex items-center gap-4 px-6 py-3 border-b border-[#334155] bg-[#1e293b]">
        <span className="text-sm font-bold tracking-wide text-blue-400">
          🏭 FABRİKA AI
        </span>
        <nav className="flex gap-1 ml-4">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={clsx(
                "px-3 py-1.5 text-xs rounded transition-colors",
                tab === t.id
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-700"
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <span className="ml-auto text-xs text-slate-500">MVP v0.2 — Faz 1</span>
      </header>

      {/* ── Ana Alan ───────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 overflow-y-auto p-6">
          {tab === "live" && <CameraGrid />}
          {tab === "dashboard" && <Dashboard />}
          {tab === "events" && (
            <p className="text-slate-500 text-sm">
              Olay listesi — Faz 4'te (Gün 15) implement edilecek.
            </p>
          )}
        </main>
        <AlarmPanel />
      </div>
    </div>
  );
}
