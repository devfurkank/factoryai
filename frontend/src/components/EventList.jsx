import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useEvents } from "../hooks/useEvents";
import clsx from "clsx";

const PAGE_SIZE = 20;

const SEVERITY_BADGE = {
  CRITICAL: "bg-red-600/20 text-red-400 border-red-600",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500",
  MEDIUM: "bg-yellow-500/20 text-yellow-300 border-yellow-500",
  LOW: "bg-slate-500/20 text-slate-300 border-slate-500",
};

const STATUS_BADGE = {
  ACTIVE: "text-red-400",
  SUSTAINED: "text-orange-400",
  RESOLVED: "text-ok",
  ESCALATED: "text-purple-400",
  PENDING: "text-slate-400",
};

const EVENT_TYPES = [
  "FORBIDDEN_ZONE_ENTRY", "PPE_VIOLATION", "FALL", "INACTIVITY",
  "FIRE", "SMOKE", "FORKLIFT_PROXIMITY", "DIRECTION_VIOLATION",
];
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-surface border border-border rounded px-2 py-1.5 text-xs text-slate-200"
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o.value ?? o} value={o.value ?? o}>
          {o.label ?? String(o).replace(/_/g, " ")}
        </option>
      ))}
    </select>
  );
}

/** Olay detay modalı — thumbnail, video klip, metadata, durum yönetimi. */
function EventDetailModal({ event, onClose }) {
  const queryClient = useQueryClient();
  const [clipFailed, setClipFailed] = useState(false);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => api.events.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      onClose();
    },
  });

  if (!event) return null;
  const isTerminal = event.status === "RESOLVED";

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-border rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold text-sm">
            {event.event_type.replace(/_/g, " ")}
            <span className={clsx("ml-3 text-xs", STATUS_BADGE[event.status])}>
              ● {event.status}
            </span>
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg leading-none">
            ✕
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Video klip (varsa) yoksa thumbnail */}
          {event.clip_path && !clipFailed ? (
            <video
              src={api.events.clipUrl(event.id)}
              controls
              autoPlay
              muted
              className="w-full rounded border border-border"
              onError={() => setClipFailed(true)}
            />
          ) : event.thumbnail_path ? (
            <img
              src={api.events.thumbnailUrl(event.id)}
              alt="olay görüntüsü"
              className="w-full rounded border border-border"
            />
          ) : (
            <p className="text-xs text-slate-500">Görüntü yok</p>
          )}
          {event.clip_path && clipFailed && (
            <p className="text-xs text-warn">
              Klip tarayıcıda oynatılamadı —{" "}
              <a href={api.events.clipUrl(event.id)} download className="text-blue-400 hover:underline">
                indirmek için tıklayın
              </a>
            </p>
          )}

          {/* Detay alanları */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
            <p><span className="text-slate-400">Kamera:</span> {event.camera_id}</p>
            <p><span className="text-slate-400">Risk:</span> {event.risk_score} · {event.severity}</p>
            <p><span className="text-slate-400">Başlangıç:</span> {formatTime(event.started_at)}</p>
            <p><span className="text-slate-400">Bitiş:</span> {formatTime(event.ended_at)}</p>
            <p><span className="text-slate-400">Bölge:</span> {event.zone_id || "—"}</p>
            <p><span className="text-slate-400">Track ID:</span> {event.track_ids?.join(", ") || "—"}</p>
            <p className="col-span-2">
              <span className="text-slate-400">Sınıflar:</span>{" "}
              {event.detected_classes?.join(", ") || "—"}
            </p>
          </div>

          {event.metadata && Object.keys(event.metadata).length > 0 && (
            <pre className="bg-black/40 border border-border rounded p-2 text-[11px] text-slate-300 overflow-x-auto">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          )}

          {/* Lifecycle aksiyonları (PENDING→ACTIVE→SUSTAINED→RESOLVED|ESCALATED) */}
          {!isTerminal && (
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => statusMutation.mutate({ id: event.id, status: "RESOLVED" })}
                disabled={statusMutation.isPending}
                className="px-3 py-1.5 text-xs rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
              >
                ✓ Çözüldü
              </button>
              {event.status !== "ESCALATED" && (
                <button
                  onClick={() => statusMutation.mutate({ id: event.id, status: "ESCALATED" })}
                  disabled={statusMutation.isPending}
                  className="px-3 py-1.5 text-xs rounded bg-purple-700 hover:bg-purple-600 text-white disabled:opacity-50"
                >
                  ↑ Yükselt
                </button>
              )}
              {statusMutation.isError && (
                <span className="text-xs text-danger self-center">Güncelleme başarısız</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EventList() {
  const [filters, setFilters] = useState({ event_type: "", severity: "", camera_id: "" });
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

  const setFilter = (key) => (value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(0);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold">
          Olaylar <span className="text-sm text-slate-500 font-normal">({total})</span>
        </h2>
        <div className="flex gap-2">
          <FilterSelect
            label="Tüm Tipler"
            value={filters.event_type}
            onChange={setFilter("event_type")}
            options={EVENT_TYPES}
          />
          <FilterSelect
            label="Tüm Önem"
            value={filters.severity}
            onChange={setFilter("severity")}
            options={SEVERITIES}
          />
          <FilterSelect
            label="Tüm Kameralar"
            value={filters.camera_id}
            onChange={setFilter("camera_id")}
            options={cameras.map((c) => ({ value: c.id, label: c.name }))}
          />
        </div>
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Yükleniyor…</p>}
      {isError && <p className="text-danger text-sm">Olaylar yüklenemedi.</p>}
      {!isLoading && !isError && events.length === 0 && (
        <p className="text-slate-500 text-sm">Filtrelere uyan olay yok.</p>
      )}

      <div className="space-y-2">
        {events.map((ev) => (
          <button
            key={ev.id}
            onClick={() => setSelected(ev)}
            className="w-full text-left bg-surface border border-border rounded-lg p-3
                       hover:border-slate-500 transition-colors flex items-center gap-3"
          >
            {ev.thumbnail_path ? (
              <img
                src={api.events.thumbnailUrl(ev.id)}
                alt=""
                loading="lazy"
                className="w-20 h-12 object-cover rounded border border-border shrink-0"
              />
            ) : (
              <div className="w-20 h-12 rounded border border-border bg-black/40 shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {ev.event_type.replace(/_/g, " ")}
                {ev.clip_path && <span className="ml-2 text-xs">🎬</span>}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                {ev.camera_id} · {formatTime(ev.started_at)}
                {ev.zone_id ? ` · ${ev.zone_id}` : ""}
              </p>
            </div>
            <span className={clsx("text-xs", STATUS_BADGE[ev.status])}>{ev.status}</span>
            <span
              className={clsx(
                "text-xs px-2 py-0.5 rounded-full border shrink-0",
                SEVERITY_BADGE[ev.severity] || SEVERITY_BADGE.LOW
              )}
            >
              {ev.risk_score} · {ev.severity}
            </span>
          </button>
        ))}
      </div>

      {/* Sayfalama */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 text-xs">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded bg-surface border border-border disabled:opacity-40 hover:border-slate-500"
          >
            ← Önceki
          </button>
          <span className="text-slate-400">
            Sayfa {page + 1} / {pageCount}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page >= pageCount - 1}
            className="px-3 py-1.5 rounded bg-surface border border-border disabled:opacity-40 hover:border-slate-500"
          >
            Sonraki →
          </button>
        </div>
      )}

      <EventDetailModal event={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
