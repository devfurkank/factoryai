import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FileText, RefreshCw, Sparkles, CalendarDays } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Spinner } from "../components/ui";
import { eventTypeLabel, formatDate, formatDateTime, CHART_COLORS } from "../lib/format";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/** Tür kırılımını yatay bar olarak gösterir. */
function BreakdownBars({ breakdown }) {
  const entries = Object.entries(breakdown || {}).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <p className="text-xs text-ink-faint">Veri yok</p>;
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-2.5">
      {entries.map(([type, count], i) => (
        <div key={type}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-ink-soft">{eventTypeLabel(type)}</span>
            <span className="font-semibold text-ink tabular-nums">{count}</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(count / max) * 100}%`,
                background: CHART_COLORS[i % CHART_COLORS.length],
              }}
            />
          </div>
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
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 animate-fade-up">
      {/* ── Ana rapor alanı ──────────────────────────────────────────────── */}
      <div className="xl:col-span-2 space-y-4">
        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-medium text-ink-faint">Rapor Tarihi</label>
              <Input
                type="date"
                value={date}
                max={todayIso()}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <Button
              onClick={() => generateMutation.mutate(Boolean(summary))}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending ? (
                <Spinner className="w-4 h-4 text-white" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              {summary ? "Yeniden Üret" : "Özet Üret"}
            </Button>
            {generateMutation.isError && (
              <p className="text-xs text-rose-600 mb-2">
                Üretim başarısız: {generateMutation.error.message}
              </p>
            )}
          </div>
        </Card>

        {isLoading ? (
          <Card><div className="flex justify-center py-16"><Spinner /></div></Card>
        ) : summary ? (
          <Card>
            <CardHeader
              title={`Günlük Güvenlik Raporu — ${formatDate(summary.summary_date)}`}
              subtitle={`Üretim: ${formatDateTime(summary.created_at)}`}
              action={
                <Badge
                  className={
                    summary.source === "gemma"
                      ? "bg-violet-50 text-violet-700 ring-violet-200"
                      : "bg-slate-100 text-slate-600 ring-slate-200"
                  }
                >
                  <Sparkles className="w-3 h-3" />
                  {summary.source === "gemma" ? "Gemma AI" : "Şablon"}
                </Badge>
              }
            />
            <div className="px-5 pb-5 space-y-5">
              {/* Özet metni */}
              <div className="bg-accent-soft/60 border border-indigo-100 rounded-xl p-4">
                <p className="text-sm text-ink leading-relaxed whitespace-pre-line">
                  {summary.summary_text}
                </p>
              </div>

              {/* Sayısal kırılım */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-line p-4">
                  <p className="text-xs text-ink-faint">Toplam Olay</p>
                  <p className="text-2xl font-bold text-ink tabular-nums mt-1">
                    {summary.total_events}
                  </p>
                </div>
                <div className="rounded-xl border border-line p-4">
                  <p className="text-xs text-ink-faint">Yüksek Riskli</p>
                  <p className="text-2xl font-bold text-rose-600 tabular-nums mt-1">
                    {summary.high_risk_events}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-ink-soft mb-3">Olay Türü Kırılımı</p>
                <BreakdownBars breakdown={summary.event_breakdown?.by_type} />
              </div>
            </div>
          </Card>
        ) : notFound ? (
          <Card>
            <EmptyState
              icon={FileText}
              title="Bu tarih için özet henüz üretilmemiş"
              hint='"Özet Üret" butonuyla seçili günün raporunu oluşturabilirsiniz. Sistem her gece 23:55te otomatik üretir.'
            />
          </Card>
        ) : error ? (
          <Card>
            <EmptyState icon={FileText} title="Rapor yüklenemedi" hint={error.message} />
          </Card>
        ) : null}
      </div>

      {/* ── Geçmiş raporlar ──────────────────────────────────────────────── */}
      <Card className="h-fit">
        <CardHeader title="Geçmiş Raporlar" subtitle="Son 14 kayıt" />
        <div className="px-2 pb-3">
          {summaries.length === 0 ? (
            <EmptyState icon={CalendarDays} title="Kayıtlı rapor yok" />
          ) : (
            summaries.map((s) => (
              <button
                key={s.summary_date}
                onClick={() => setDate(s.summary_date)}
                className={clsx(
                  "w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl transition-colors text-left",
                  s.summary_date === date ? "bg-accent-soft" : "hover:bg-slate-50"
                )}
              >
                <div>
                  <p className="text-sm font-medium text-ink">{formatDate(s.summary_date)}</p>
                  <p className="text-[11px] text-ink-faint">
                    {s.total_events} olay · {s.high_risk_events} yüksek riskli
                  </p>
                </div>
                <FileText className="w-4 h-4 text-ink-faint shrink-0" />
              </button>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
