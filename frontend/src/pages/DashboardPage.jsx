import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import clsx from "clsx";
import { api } from "../api/client";
import { Card, CardHeader, StatCard, Badge, EmptyState, Spinner } from "../components/ui";
import Icon from "../components/Icon";
import {
  eventTypeLabel, SEVERITY_META, STATUS_META, CHART_COLORS, formatDateTime,
} from "../lib/format";

/** Recharts tooltip'i — Glacier koyu tema kartı. */
function ChartTooltip({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-panel-elevated rounded-lg px-3 py-2 text-xs">
      <p className="font-semibold text-on-surface mb-1">
        {labelFormatter ? labelFormatter(label) : label}
      </p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-on-surface-variant">
          <span
            className="inline-block w-2 h-2 rounded-full mr-1.5"
            style={{ background: p.color || p.fill }}
          />
          {p.name}: <span className="font-medium text-on-surface">{p.value}</span>
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
    <div className="space-y-8 animate-fade-up">
      <div>
        <h2 className="text-2xl font-headline font-bold text-on-surface tracking-tight">Dashboard Overview</h2>
        <p className="text-on-surface-variant text-sm mt-1">Sistem durumu ve son güvenlik olayları özeti.</p>
      </div>

      {/* ── KPI kartları (bento) ─────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon="event"
          label="Bugünkü Olay"
          value={daily?.total ?? "—"}
          sub={daily?.date}
          tone="primary"
        />
        <StatCard
          icon="warning"
          label="Yüksek Riskli"
          value={daily?.high_risk_events ?? "—"}
          sub="Hemen müdahale gerekli"
          tone="error"
        />
        <StatCard
          icon="pending_actions"
          label="Aktif (Çözülmemiş)"
          value={activeEvents?.total ?? "—"}
          sub="İncelenmeyi bekliyor"
          tone="tertiary"
        />
        <StatCard
          icon="videocam"
          label="Aktif Kamera"
          value={health?.cameras ?? "—"}
          sub={health?.status === "ok" ? "Tüm sistemler çevrimiçi" : "Servis durumu kontrol edin"}
          tone="secondary"
        />
      </div>

      {/* ── Grafikler + yan panel ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-semibold text-on-surface flex items-center gap-2">
                <Icon name="show_chart" className="text-primary text-sm" />
                Olay Trendi (Son 7 Gün)
              </h3>
              <Link to="/events" className="text-xs px-3 py-1 rounded bg-surface-container-high border border-outline-variant hover:border-primary/50 text-on-surface-variant transition-colors">
                Detaylar
              </Link>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7dd3fc" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#7dd3fc" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ff6b6b" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#ff6b6b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} dy={6} />
                  <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="total" name="Toplam" stroke="#7dd3fc"
                        strokeWidth={2} fill="url(#gTotal)" />
                  <Area type="monotone" dataKey="high_risk" name="Yüksek Riskli" stroke="#ff6b6b"
                        strokeWidth={2} fill="url(#gHigh)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-semibold text-on-surface flex items-center gap-2">
                <Icon name="bar_chart" className="text-tertiary text-sm" />
                Saatlik Dağılım
              </h3>
            </div>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourData} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} dy={6} interval={2} />
                  <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip content={<ChartTooltip labelFormatter={(l) => `${l}:00 – ${l}:59`} />} />
                  <Bar dataKey="total" name="Toplam" fill="#7dd3fc" radius={[4, 4, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="high_risk" name="Yüksek Riskli" fill="#ff6b6b" radius={[4, 4, 0, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-1 space-y-6">
          <Card className="p-6 glass-panel-elevated">
            <h3 className="text-lg font-semibold text-on-surface mb-6 flex items-center gap-2">
              <Icon name="pie_chart" className="text-secondary text-sm" />
              Tür Dağılımı
            </h3>
            <div className="h-40 w-full mb-6">
              {typeData.length === 0 ? (
                <EmptyState icon="donut_large" title="Bugün olay yok" hint="Olaylar geldikçe dağılım burada görünür." />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={typeData} dataKey="value" nameKey="name"
                      cx="50%" cy="50%" innerRadius={52} outerRadius={78}
                      paddingAngle={3} strokeWidth={0}
                    >
                      {typeData.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
            {typeData.length > 0 && (
              <div className="space-y-3">
                {typeData.map((t, i) => (
                  <div key={t.name} className="flex justify-between items-center text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
                      />
                      <span className="text-on-surface-variant">{t.name}</span>
                    </div>
                    <span className="font-semibold text-on-surface">{t.value}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-on-surface flex items-center gap-2">
                <Icon name="list_alt" className="text-primary text-sm" />
                Son Olaylar
              </h3>
              <Link to="/events" className="text-xs text-primary hover:text-primary-fixed transition-colors">
                Tümü
              </Link>
            </div>
            {recentLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : (recent?.items ?? []).length === 0 ? (
              <EmptyState icon="event_busy" title="Henüz olay yok" />
            ) : (
              <div className="space-y-1">
                {(recent?.items ?? []).map((ev) => {
                  const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
                  const st = STATUS_META[ev.status] || STATUS_META.ACTIVE;
                  return (
                    <Link
                      key={ev.id}
                      to="/events"
                      className="group flex items-start gap-3 p-3 rounded-lg hover:bg-surface-container-high/50 transition-colors border border-transparent hover:border-outline-variant/30"
                    >
                      <div className={clsx("mt-1 w-2 h-2 rounded-full shrink-0", sev.dot)} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-on-surface truncate">
                          {eventTypeLabel(ev.event_type)}
                        </p>
                        <p className="text-xs text-on-surface-variant truncate">
                          {ev.camera_id} · {formatDateTime(ev.started_at)}
                        </p>
                      </div>
                      <Badge className={st.badge}>{st.label}</Badge>
                    </Link>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
