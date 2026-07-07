import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../api/client";
import { useEvents } from "../hooks/useEvents";
import { Badge, Button, Card, EmptyState, Select, Spinner, Input } from "../components/ui";
import Icon from "../components/Icon";
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
    <div className="flex flex-col gap-6 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="text-2xl font-headline font-semibold text-on-surface mb-1">Olaylar</h2>
          <p className="text-on-surface-variant text-sm">
            Sistem tarafından tespit edilen tüm güvenlik ihlalleri ve uyarılar.
          </p>
        </div>
        <p className="text-xs text-on-surface-variant">
          <span className="font-semibold text-on-surface">{total}</span> olay
        </p>
      </div>

      {/* Filtre çubuğu */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 min-w-[150px] flex-1">
            <label className="text-xs text-on-surface-variant ml-1">Olay Türü</label>
            <Select value={filters.event_type} onChange={setFilter("event_type")}>
              <option value="">Tümü</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>{eventTypeLabel(t)}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1 min-w-[120px] flex-1">
            <label className="text-xs text-on-surface-variant ml-1">Önem</label>
            <Select value={filters.severity} onChange={setFilter("severity")}>
              <option value="">Tümü</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{SEVERITY_META[s].label}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1 min-w-[120px] flex-1">
            <label className="text-xs text-on-surface-variant ml-1">Durum</label>
            <Select value={filters.status} onChange={setFilter("status")}>
              <option value="">Tümü</option>
              {Object.entries(STATUS_META).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1 min-w-[150px] flex-1">
            <label className="text-xs text-on-surface-variant ml-1">Kamera</label>
            <Select value={filters.camera_id} onChange={setFilter("camera_id")}>
              <option value="">Tüm Kameralar</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-on-surface-variant ml-1">Başlangıç</label>
            <Input type="date" value={filters.from_date} onChange={setFilter("from_date")} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-on-surface-variant ml-1">Bitiş</label>
            <Input type="date" value={filters.to_date} onChange={setFilter("to_date")} />
          </div>
          {hasFilter && (
            <Button
              variant="secondary"
              onClick={() => { setFilters(EMPTY_FILTERS); setPage(0); }}
            >
              <Icon name="filter_alt_off" className="text-sm" /> Filtreleri Temizle
            </Button>
          )}
        </div>
      </Card>

      {/* Tablo + detay paneli */}
      <div className="flex-1 flex gap-6 min-h-0">
        <Card className="flex-1 flex flex-col overflow-hidden">
          <div className="overflow-auto flex-1">
            {isLoading ? (
              <div className="flex justify-center py-16"><Spinner /></div>
            ) : isError ? (
              <EmptyState icon="report" title="Olaylar yüklenemedi" hint="Backend bağlantısını kontrol edin." />
            ) : events.length === 0 ? (
              <EmptyState
                icon="notifications_active"
                title="Filtrelere uyan olay yok"
                hint={hasFilter ? "Filtreleri temizleyip tekrar deneyin." : "Sistem olay ürettikçe burada listelenir."}
              />
            ) : (
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-surface-container-high/90 backdrop-blur-md z-10">
                  <tr>
                    <th className="py-3 px-4 text-xs font-semibold text-on-surface-variant border-b border-outline-variant/30">Olay Türü</th>
                    <th className="py-3 px-4 text-xs font-semibold text-on-surface-variant border-b border-outline-variant/30 hidden md:table-cell">Kamera</th>
                    <th className="py-3 px-4 text-xs font-semibold text-on-surface-variant border-b border-outline-variant/30 hidden lg:table-cell">Tarih/Saat</th>
                    <th className="py-3 px-4 text-xs font-semibold text-on-surface-variant border-b border-outline-variant/30">Risk Puanı</th>
                    <th className="py-3 px-4 text-xs font-semibold text-on-surface-variant border-b border-outline-variant/30 hidden sm:table-cell">Durum</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-outline-variant/20">
                  {events.map((ev) => {
                    const sev = SEVERITY_META[ev.severity] || SEVERITY_META.LOW;
                    const st = STATUS_META[ev.status] || STATUS_META.ACTIVE;
                    const isSelected = selected?.id === ev.id;
                    return (
                      <tr
                        key={ev.id}
                        onClick={() => setSelected(ev)}
                        className={clsx(
                          "cursor-pointer transition-colors relative",
                          isSelected ? "bg-primary/10 hover:bg-primary/15" : "hover:bg-surface-variant/50"
                        )}
                      >
                        <td className="py-3 px-4 relative">
                          {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary" />}
                          <div className="flex items-center gap-3">
                            {ev.thumbnail_path ? (
                              <img
                                src={api.events.thumbnailUrl(ev.id)}
                                alt=""
                                loading="lazy"
                                className="w-10 h-10 object-cover rounded-full border border-outline-variant/30 shrink-0"
                              />
                            ) : (
                              <div className={clsx("w-8 h-8 rounded-full flex items-center justify-center shrink-0", sev.badge)}>
                                <Icon name="warning" className="text-sm" />
                              </div>
                            )}
                            <span className="font-medium text-on-surface">{eventTypeLabel(ev.event_type)}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-on-surface-variant hidden md:table-cell">{ev.camera_id}</td>
                        <td className="py-3 px-4 text-on-surface-variant text-xs hidden lg:table-cell whitespace-nowrap">
                          {formatDateTime(ev.started_at)}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <span className={clsx("font-semibold", sev.dot.replace("bg-", "text-"))}>{ev.risk_score}</span>
                            <div className="w-16 h-1.5 bg-surface-container rounded-full overflow-hidden hidden xl:block">
                              <div className={clsx("h-full", sev.dot)} style={{ width: `${ev.risk_score}%` }} />
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 hidden sm:table-cell">
                          <Badge className={st.badge}>{st.label}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Sayfalama */}
          {total > PAGE_SIZE && (
            <div className="bg-surface-container-low/50 border-t border-outline-variant/30 p-3 flex items-center justify-between">
              <span className="text-xs text-on-surface-variant">Toplam {total} olay</span>
              <div className="flex items-center gap-4">
                <span className="text-xs text-on-surface">Sayfa {page + 1} / {pageCount}</span>
                <div className="flex gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="w-8 h-8 rounded bg-surface border border-outline-variant/30 flex items-center justify-center text-on-surface-variant hover:text-primary hover:border-primary/50 transition-colors disabled:opacity-50"
                  >
                    <Icon name="chevron_left" className="text-sm" />
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={page >= pageCount - 1}
                    className="w-8 h-8 rounded bg-surface border border-outline-variant/30 flex items-center justify-center text-on-surface-variant hover:text-primary hover:border-primary/50 transition-colors disabled:opacity-50"
                  >
                    <Icon name="chevron_right" className="text-sm" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </Card>

        {selected && <EventDetailModal event={selected} onClose={() => setSelected(null)} />}
      </div>
    </div>
  );
}
