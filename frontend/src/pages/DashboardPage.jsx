import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  ShieldAlert, Flame, Cctv, CircleAlert, ArrowRight,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import { Card, CardHeader, StatCard, Badge, EmptyState, Spinner } from "../components/ui";
import {
  eventTypeLabel, SEVERITY_META, STATUS_META, CHART_COLORS, formatDateTime,
} from "../lib/format";

/** Recharts tooltip'i — açık tema kartı. */
function ChartTooltip({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface border border-line rounded-xl shadow-pop px-3 py-2 text-xs">
      <p className="font-semibold text-ink mb-1">
        {labelFormatter ? labelFormatter(label) : label}
      </p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-ink-soft">
          <span
            className="inline-block w-2 h-2 rounded-full mr-1.5"
            style={{ background: p.color || p.fill }}
          />
          {p.name}: <span className="font-medium text-ink">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const { data: health } = useQuery({
    queryKey: ["health"], queryFn: api.health, refetchInterval: 15000,
  });
  const { data: daily } = useQuery({
    queryKey: ["events-daily-stats"], queryFn: api.events.dailyStats, refetchInterval: 30000,
  });
  const { data: hourly } = useQuery({
    queryKey: ["events-hourly-stats"], queryFn: api.events.hourlyStats, refetchInterval: 60000,
  });
  const { data: range } = useQuery({
    queryKey: ["events-range-stats"], queryFn: () => api.events.rangeStats(7), refetchInterval: 300000,
  });
  const { data: activeEvents } = useQuery({
    queryKey: ["events", { status: "ACTIVE", limit: 1 }],
    queryFn: () => api.events.list({ status: "ACTIVE", limit: 1 }),
    refetchInterval: 30000,
  });
  const { data: recent, isLoading: recentLoading } = useQuery({
    queryKey: ["events", { limit: 6 }],
    queryFn: () => api.events.list({ limit: 6 }),
    refetchInterval: 15000,
  });

  const trendData = (range?.days ?? []).map((d) => ({
    ...d,
    label: new Date(d.date + "T00:00:00").toLocaleDateString("tr-TR", {
      day: "2-digit", month: "2-digit",
    }),
  }));
  const hourData = (hourly?.hours ?? []).map((h) => ({
    ...h,
    label: `${String(h.hour).padStart(2, "0")}`,
  }));
  const typeData = Object.entries(daily?.by_type ?? {}).map(([type, count]) => ({
    name: eventTypeLabel(type),
    value: count,
  }));

  return (
    <div className="space-y-6 animate-fade-up">
      {/* ── KPI kartları ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={ShieldAlert}
          label="Bugünkü Olay"
          value={daily?.total ?? "—"}
          sub={daily?.date}
          tone="indigo"
        />
        <StatCard
          icon={Flame}
          label="Yüksek Riskli"
          value={daily?.high_risk_events ?? "—"}
          sub="Risk puanı ≥ 70"
          tone="rose"
        />
        <StatCard
          icon={CircleAlert}
          label="Aktif (Çözülmemiş)"
          value={activeEvents?.total ?? "—"}
          sub="Müdahale bekliyor"
          tone="amber"
        />
        <StatCard
          icon={Cctv}
          label="Aktif Kamera"
          value={health?.cameras ?? "—"}
          sub={health?.status === "ok" ? "Tüm servisler çalışıyor" : "Servis durumu kontrol edin"}
          tone="emerald"
        />
      </div>

      {/* ── Grafikler: 7 günlük trend + tür dağılımı ─────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title="Olay Trendi" subtitle="Son 7 gün — toplam ve yüksek riskli" />
          <div className="px-3 pb-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#4f46e5" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} strokeDasharray="0" />
                <XAxis dataKey="label" axisLine={false} tickLine={false} dy={6} />
                <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="total" name="Toplam" stroke="#4f46e5"
                      strokeWidth={2} fill="url(#gTotal)" />
                <Area type="monotone" dataKey="high_risk" name="Yüksek Riskli" stroke="#f43f5e"
                      strokeWidth={2} fill="url(#gHigh)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Tür Dağılımı" subtitle="Bugün" />
          <div className="px-3 pb-4 h-64">
            {typeData.length === 0 ? (
              <EmptyState title="Bugün olay yok" hint="Olaylar geldikçe dağılım burada görünür." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={typeData} dataKey="value" nameKey="name"
                    cx="50%" cy="45%" innerRadius={52} outerRadius={78}
                    paddingAngle={3} strokeWidth={0}
                  >
                    {typeData.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle" iconSize={8}
                    formatter={(v) => <span className="text-xs text-ink-soft">{v}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {/* ── Saatlik dağılım + son olaylar ────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader title="Saatlik Dağılım" subtitle="Bugün (UTC) — saat bazında olay sayısı" />
          <div className="px-3 pb-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourData} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" axisLine={false} tickLine={false} dy={6} interval={2} />
                <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<ChartTooltip labelFormatter={(l) => `${l}:00 – ${l}:59`} />} />
                <Bar dataKey="total" name="Toplam" fill="#4f46e5" radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="high_risk" name="Yüksek Riskli" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Son Olaylar"
            action={
              <Link
                to="/events"
                className="text-xs font-medium text-accent hover:text-accent-strong flex items-center gap-1"
              >
                Tümü <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          />
          <div className="px-2 pb-3">
            {recentLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : (recent?.items ?? []).length === 0 ? (
              <EmptyState title="Henüz olay yok" />
            ) : (
              (recent?.items ?? []).map((ev) => {
                const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
                const st = STATUS_META[ev.status] || STATUS_META.ACTIVE;
                return (
                  <Link
                    key={ev.id}
                    to="/events"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 transition-colors"
                  >
                    <span className={clsx("w-2 h-2 rounded-full shrink-0", sev.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-ink truncate">
                        {eventTypeLabel(ev.event_type)}
                      </p>
                      <p className="text-[11px] text-ink-faint">
                        {ev.camera_id} · {formatDateTime(ev.started_at)}
                      </p>
                    </div>
                    <Badge className={st.badge}>{st.label}</Badge>
                  </Link>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
