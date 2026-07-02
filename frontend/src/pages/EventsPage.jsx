import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ChevronLeft, ChevronRight, Clapperboard, ShieldAlert, FilterX,
} from "lucide-react";
import { api } from "../api/client";
import { useEvents } from "../hooks/useEvents";
import { Badge, Button, Card, EmptyState, Select, Spinner, Input } from "../components/ui";
import EventDetailModal from "../components/events/EventDetailModal";
import {
  EVENT_TYPES, eventTypeLabel, formatDateTime,
  SEVERITY_META, SEVERITIES, STATUS_META,
} from "../lib/format";

const PAGE_SIZE = 15;

const EMPTY_FILTERS = {
  event_type: "", severity: "", camera_id: "", status: "",
  from_date: "", to_date: "",
};

export default function EventsPage() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(null);

  const { data: cameras = [] } = useQuery({
    queryKey: ["cameras"],
    queryFn: api.cameras.list,
  });

  // Boş filtreleri query string'e taşıma
  const activeFilters = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== "")
  );
  const { data, isLoading, isError } = useEvents({
    ...activeFilters,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const events = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilter = Object.values(filters).some((v) => v !== "");

  const setFilter = (key) => (e) => {
    setFilters((f) => ({ ...f, [key]: e.target.value }));
    setPage(0);
  };

  return (
    <div className="space-y-4 animate-fade-up">
      {/* ── Filtre çubuğu ─────────────────────────────────────────────────── */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Olay Türü</label>
            <Select value={filters.event_type} onChange={setFilter("event_type")}>
              <option value="">Tümü</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>{eventTypeLabel(t)}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Önem</label>
            <Select value={filters.severity} onChange={setFilter("severity")}>
              <option value="">Tümü</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{SEVERITY_META[s].label}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Durum</label>
            <Select value={filters.status} onChange={setFilter("status")}>
              <option value="">Tümü</option>
              {Object.entries(STATUS_META).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Kamera</label>
            <Select value={filters.camera_id} onChange={setFilter("camera_id")}>
              <option value="">Tümü</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Başlangıç</label>
            <Input type="date" value={filters.from_date} onChange={setFilter("from_date")} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-ink-faint">Bitiş</label>
            <Input type="date" value={filters.to_date} onChange={setFilter("to_date")} />
          </div>
          {hasFilter && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setFilters(EMPTY_FILTERS); setPage(0); }}
              className="mb-0.5"
            >
              <FilterX className="w-4 h-4" /> Temizle
            </Button>
          )}
          <p className="ml-auto text-xs text-ink-faint mb-2">
            <span className="font-semibold text-ink">{total}</span> olay
          </p>
        </div>
      </Card>

      {/* ── Olay tablosu ──────────────────────────────────────────────────── */}
      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : isError ? (
          <EmptyState icon={ShieldAlert} title="Olaylar yüklenemedi" hint="Backend bağlantısını kontrol edin." />
        ) : events.length === 0 ? (
          <EmptyState
            icon={ShieldAlert}
            title="Filtrelere uyan olay yok"
            hint={hasFilter ? "Filtreleri temizleyip tekrar deneyin." : "Sistem olay ürettikçe burada listelenir."}
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-slate-50/60">
                <th className="text-left font-medium text-ink-faint text-xs px-5 py-3">Olay</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden md:table-cell">Kamera</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden lg:table-cell">Zaman</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3">Risk</th>
                <th className="text-left font-medium text-ink-faint text-xs px-4 py-3 hidden sm:table-cell">Durum</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => {
                const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
                const st = STATUS_META[ev.status] || STATUS_META.ACTIVE;
                return (
                  <tr
                    key={ev.id}
                    onClick={() => setSelected(ev)}
                    className="border-b border-line last:border-0 hover:bg-slate-50/80 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        {ev.thumbnail_path ? (
                          <img
                            src={api.events.thumbnailUrl(ev.id)}
                            alt=""
                            loading="lazy"
                            className="w-16 h-10 object-cover rounded-lg border border-line shrink-0"
                          />
                        ) : (
                          <div className="w-16 h-10 rounded-lg border border-line bg-slate-100 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="font-medium text-ink truncate flex items-center gap-1.5">
                            {eventTypeLabel(ev.event_type)}
                            {ev.clip_path && (
                              <Clapperboard className="w-3.5 h-3.5 text-accent shrink-0" />
                            )}
                          </p>
                          {ev.zone_id && (
                            <p className="text-[11px] text-ink-faint truncate">{ev.zone_id}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-soft hidden md:table-cell">{ev.camera_id}</td>
                    <td className="px-4 py-3 text-ink-soft hidden lg:table-cell whitespace-nowrap">
                      {formatDateTime(ev.started_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge className={sev.badge}>
                        <span className={clsx("w-1.5 h-1.5 rounded-full", sev.dot)} />
                        {ev.risk_score}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <Badge className={st.badge}>{st.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* Sayfalama */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-line">
            <p className="text-xs text-ink-faint">
              Sayfa <span className="font-medium text-ink">{page + 1}</span> / {pageCount}
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary" size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft className="w-4 h-4" /> Önceki
              </Button>
              <Button
                variant="secondary" size="sm"
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={page >= pageCount - 1}
              >
                Sonraki <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {selected && <EventDetailModal event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
