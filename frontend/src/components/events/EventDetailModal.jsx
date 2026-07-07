import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../../api/client";
import { Badge, Button } from "../ui";
import Icon from "../Icon";
import {
  eventTypeLabel, formatDateTime, SEVERITY_META, STATUS_META,
} from "../../lib/format";

function DetailRow({ label, value }) {
  return (
    <div>
      <span className="block text-[10px] text-on-surface-variant uppercase tracking-wider mb-1">{label}</span>
      <span className="text-sm text-on-surface break-all">{value ?? "—"}</span>
    </div>
  );
}

/** Olay detayı — yan panel: klip/tespit fotoğrafı sekmeleri, metadata ve lifecycle aksiyonları. */
export default function EventDetailModal({ event, onClose }) {
  const queryClient = useQueryClient();
  const [clipFailed, setClipFailed] = useState(false);
  const [mediaTab, setMediaTab] = useState("clip");

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => api.events.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      onClose();
    },
  });

  if (!event) return null;
  const sev = SEVERITY_META[event.severity] || SEVERITY_META.LOW;
  const st = STATUS_META[event.status] || STATUS_META.ACTIVE;
  const isTerminal = event.status === "RESOLVED";

  // Medya kaynakları: klip (oynatılabiliyorsa) + tespit fotoğrafı (thumbnail).
  // İkisi de varsa sekmelerle geçiş yapılır; tek kaynak varsa doğrudan o gösterilir.
  const hasClip = Boolean(event.clip_path) && !clipFailed;
  const hasPhoto = Boolean(event.thumbnail_path);
  const activeMedia = hasClip ? (hasPhoto && mediaTab === "photo" ? "photo" : "clip") : "photo";

  return (
    <div className="w-[360px] shrink-0 glass-panel-elevated rounded-xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-primary/10 flex justify-between items-start bg-primary/5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Icon name="warning" className="text-error text-sm" />
            <h3 className="text-lg font-semibold text-on-surface">{eventTypeLabel(event.event_type)}</h3>
          </div>
          <span className="text-xs text-on-surface-variant break-all">ID: {event.id}</span>
        </div>
        <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface shrink-0">
          <Icon name="close" className="text-sm" />
        </button>
      </div>

      <div className="overflow-y-auto flex-1 p-4 flex flex-col gap-5">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge className={sev.badge}>Risk {event.risk_score} · {sev.label}</Badge>
          <Badge className={st.badge}>{st.label}</Badge>
        </div>

        {/* Medya sekmeleri */}
        {hasClip && hasPhoto && (
          <div className="flex bg-surface-container-highest rounded-lg p-1">
            {[
              { id: "clip", label: "Video Klip" },
              { id: "photo", label: "Tespit Fotoğrafı" },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setMediaTab(id)}
                className={clsx(
                  "flex-1 py-1.5 text-xs font-medium rounded transition-colors",
                  activeMedia === id
                    ? "bg-primary/20 text-primary border border-primary/20 shadow-sm"
                    : "text-on-surface-variant hover:text-on-surface"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Video klip / tespit fotoğrafı / boş durum */}
        {activeMedia === "clip" && hasClip ? (
          <video
            src={api.events.clipUrl(event.id)}
            controls
            autoPlay
            muted
            className="w-full rounded-lg border border-outline-variant/30 bg-black"
            onError={() => setClipFailed(true)}
          />
        ) : hasPhoto ? (
          <img
            src={api.events.thumbnailUrl(event.id)}
            alt="tespit fotoğrafı"
            className="w-full rounded-lg border border-outline-variant/30"
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-10 bg-surface-container-low rounded-lg border border-outline-variant/30 text-on-surface-variant">
            <Icon name="image_not_supported" className="text-2xl mb-2" />
            <p className="text-xs">Bu olay için görüntü yok</p>
          </div>
        )}
        {event.clip_path && clipFailed && (
          <p className="text-xs text-tertiary">
            Klip tarayıcıda oynatılamadı —{" "}
            <a
              href={api.events.clipUrl(event.id)}
              download
              className="text-primary font-medium hover:underline inline-flex items-center gap-1"
            >
              <Icon name="download" className="text-xs" /> indirmek için tıklayın
            </a>
          </p>
        )}

        {/* Detay alanları */}
        <div className="grid grid-cols-2 gap-4 bg-surface/40 p-3 rounded-lg border border-outline-variant/20">
          <DetailRow label="Kamera" value={event.camera_id} />
          <DetailRow label="Bölge" value={event.zone_id} />
          <DetailRow label="Başlangıç" value={formatDateTime(event.started_at)} />
          <DetailRow label="Bitiş" value={event.ended_at ? formatDateTime(event.ended_at) : "Devam Ediyor"} />
          <DetailRow label="Takip ID" value={event.track_ids?.join(", ")} />
          <DetailRow label="Sınıflar" value={event.detected_classes?.join(", ")} />
        </div>

        {event.metadata && Object.keys(event.metadata).length > 0 && (
          <details className="group">
            <summary className="text-xs font-medium text-on-surface-variant cursor-pointer hover:text-on-surface">
              Teknik metadata
            </summary>
            <pre className="mt-2 bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-[11px] text-on-surface-variant overflow-x-auto">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {/* Aksiyonlar */}
      {!isTerminal && (
        <div className="p-4 border-t border-outline-variant/30 flex gap-3 bg-surface-container-lowest">
          <Button
            size="sm"
            className="flex-1 !bg-emerald-500/20 !text-emerald-400 !border-emerald-500/30 hover:!bg-emerald-500/30"
            onClick={() => statusMutation.mutate({ id: event.id, status: "RESOLVED" })}
            disabled={statusMutation.isPending}
          >
            <Icon name="check_circle" className="text-sm" /> Çözüldü İşaretle
          </Button>
          {event.status !== "ESCALATED" && (
            <Button
              size="sm"
              variant="danger"
              className="flex-1"
              onClick={() => statusMutation.mutate({ id: event.id, status: "ESCALATED" })}
              disabled={statusMutation.isPending}
            >
              <Icon name="priority_high" className="text-sm" /> Yükselt
            </Button>
          )}
        </div>
      )}
      {statusMutation.isError && (
        <p className="text-xs text-error px-4 pb-3 bg-surface-container-lowest">Güncelleme başarısız</p>
      )}
    </div>
  );
}
