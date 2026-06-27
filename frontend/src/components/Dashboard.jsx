import { useDailyStats } from "../hooks/useEvents";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

function StatCard({ label, value, color = "text-white" }) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value ?? "—"}</p>
    </div>
  );
}

export default function Dashboard() {
  const { data: stats } = useDailyStats();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Genel Durum</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Aktif Kamera" value={health?.cameras} color="text-accent" />
        <StatCard label="Bugünkü Olay" value={stats?.total ?? 0} />
        <StatCard label="Yüksek Riskli" value={stats?.high_risk_events ?? 0} color="text-warn" />
        <StatCard label="WebSocket" value={health?.active_ws ?? 0} color="text-ok" />
      </div>
      <div className="bg-surface border border-border rounded-lg p-4">
        <p className="text-xs text-slate-400 mb-2">Sistem Durumu</p>
        <p className="text-sm text-ok">
          {health?.status === "ok" ? "✓ Tüm servisler çalışıyor" : "Bağlanılamıyor"}
        </p>
        <p className="text-xs text-slate-500 mt-1">Ortam: {health?.env ?? "—"}</p>
      </div>
    </div>
  );
}
