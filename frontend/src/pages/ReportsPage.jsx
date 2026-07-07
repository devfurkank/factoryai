import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Spinner } from "../components/ui";
import Icon from "../components/Icon";
import { eventTypeLabel, formatDate, formatDateTime, CHART_COLORS } from "../lib/format";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/** Tür kırılımını yatay bar olarak gösterir. */
function BreakdownBars({ breakdown }) {
  const entries = Object.entries(breakdown || {}).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <p className="text-xs text-on-surface-variant">Veri yok</p>;
  return (
    <div className="flex-1 flex flex-col justify-center gap-3">
      {entries.map(([type, count], i) => (
        <div
          key={type}
          className="flex items-center justify-between p-3 rounded-lg bg-surface-container-high/50 border border-outline-variant/30"
        >
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
            <span className="text-sm text-on-surface">{eventTypeLabel(type)}</span>
          </div>
          <span className="font-semibold" style={{ color: CHART_COLORS[i % CHART_COLORS.length] }}>{count}</span>
        </div>
      ))}
    </div>
  );
}

export default function ReportsPage() {
  const [date, setDate] = useState(todayIso());
  const queryClient = useQueryClient();

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ["summary", date],
    queryFn: () => api.summary.daily(date),
    retry: false, // 404 = henüz üretilmemiş, tekrar deneme
  });

  const { data: summaries = [] } = useQuery({
    queryKey: ["summaries"],
    queryFn: () => api.summary.list(14),
  });

  const generateMutation = useMutation({
    mutationFn: (force) => api.summary.generate(date, force),
    onSuccess: (row) => {
      queryClient.setQueryData(["summary", date], row);
      queryClient.invalidateQueries({ queryKey: ["summaries"] });
    },
  });

  const notFound = error && String(error.message).includes("özet yok");

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Action Bar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="text-3xl font-headline font-semibold text-primary mb-2">Güvenlik Raporları</h2>
          <p className="text-on-surface-variant text-sm">Sistem olayları ve AI analiz özetleri.</p>
        </div>
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-on-surface-variant ml-1">Rapor Tarihi</label>
            <Input type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} />
          </div>
          <Button
            variant="primary"
            onClick={() => generateMutation.mutate(Boolean(summary))}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? <Spinner className="text-sm" /> : <Icon name={summary ? "refresh" : "auto_awesome"} className="text-sm" />}
            {summary ? "Yeniden Üret" : "Özet Üret"}
          </Button>
        </div>
      </div>
      {generateMutation.isError && (
        <p className="text-xs text-error -mt-4">Üretim başarısız: {generateMutation.error.message}</p>
      )}

      {/* Bento Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* AI Summary Card */}
        <div className="col-span-12 lg:col-span-8 glass-panel-elevated rounded-xl p-6 flex flex-col relative overflow-hidden">
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
          {isLoading ? (
            <div className="flex justify-center py-16"><Spinner /></div>
          ) : summary ? (
            <>
              <div className="flex items-center gap-3 mb-6 border-b border-primary/10 pb-4 flex-wrap">
                <Icon name="summarize" className="text-primary text-2xl" />
                <h3 className="text-xl font-semibold text-on-surface">
                  Günlük Güvenlik Özeti — {formatDate(summary.summary_date)}
                </h3>
                <Badge
                  className={
                    summary.source === "gemma"
                      ? "bg-tertiary/20 text-tertiary border-tertiary/30 ml-auto"
                      : "bg-surface-container-high text-on-surface-variant border-outline-variant/50 ml-auto"
                  }
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                  Oluşturulma: {formatDateTime(summary.created_at)} · Kaynak: {summary.source === "gemma" ? "Gemma" : "Şablon"}
                </Badge>
              </div>
              <div className="flex-1 text-on-surface-variant text-sm leading-relaxed space-y-4 whitespace-pre-line">
                {summary.summary_text}
              </div>
              <div className="grid grid-cols-2 gap-4 mt-6 pt-4 border-t border-primary/10">
                <div>
                  <p className="text-xs text-on-surface-variant">Toplam Olay</p>
                  <p className="text-2xl font-bold text-on-surface tabular-nums mt-1">{summary.total_events}</p>
                </div>
                <div>
                  <p className="text-xs text-on-surface-variant">Yüksek Riskli</p>
                  <p className="text-2xl font-bold text-error tabular-nums mt-1">{summary.high_risk_events}</p>
                </div>
              </div>
            </>
          ) : notFound ? (
            <EmptyState
              icon="summarize"
              title="Bu tarih için özet henüz üretilmemiş"
              hint='"Özet Üret" butonuyla seçili günün raporunu oluşturabilirsiniz. Sistem her gece 23:55te otomatik üretir.'
            />
          ) : error ? (
            <EmptyState icon="error" title="Rapor yüklenemedi" hint={error.message} />
          ) : null}
        </div>

        {/* Breakdown */}
        <div className="col-span-12 lg:col-span-4 glass-panel rounded-xl p-6 flex flex-col">
          <h3 className="text-lg font-semibold text-on-surface mb-6 flex items-center gap-2">
            <Icon name="pie_chart" className="text-tertiary" />
            Tür Kırılımı
          </h3>
          {summary ? (
            <BreakdownBars breakdown={summary.event_breakdown?.by_type} />
          ) : (
            <EmptyState icon="pie_chart" title="Veri yok" hint="Önce bir özet üretin." />
          )}
        </div>
      </div>

      {/* Past Reports List */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-on-surface mb-4 flex items-center gap-2">
          <Icon name="history" className="text-secondary" />
          Geçmiş Raporlar
        </h3>
        {summaries.length === 0 ? (
          <EmptyState icon="calendar_month" title="Kayıtlı rapor yok" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-on-surface-variant">
              <thead className="text-xs uppercase bg-surface-container/50 border-b border-primary/10">
                <tr>
                  <th className="px-4 py-3 font-medium">Tarih</th>
                  <th className="px-4 py-3 font-medium">Özet Bilgi</th>
                  <th className="px-4 py-3 font-medium">Kaynak</th>
                  <th className="px-4 py-3 font-medium text-right">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-primary/5">
                {summaries.map((s) => (
                  <tr key={s.summary_date} className={clsx("hover:bg-surface-container-highest/30 transition-colors", s.summary_date === date && "bg-primary/5")}>
                    <td className="px-4 py-3 font-medium text-on-surface">{formatDate(s.summary_date)}</td>
                    <td className="px-4 py-3">{s.total_events} olay · {s.high_risk_events} yüksek riskli</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 rounded bg-tertiary/10 text-tertiary text-xs border border-tertiary/20">
                        {s.source === "gemma" ? "Gemma" : "Şablon"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => setDate(s.summary_date)} className="text-primary hover:text-primary-fixed p-1">
                        <Icon name="visibility" className="text-lg" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
