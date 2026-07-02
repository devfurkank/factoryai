import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  CheckCircle2, ArrowUpCircle, Download, ImageOff, Clapperboard, Image as ImageIcon,
} from "lucide-react";
import { api } from "../../api/client";
import { Badge, Button, Modal } from "../ui";
import {
  eventTypeLabel, formatDateTime, SEVERITY_META, STATUS_META,
} from "../../lib/format";

function DetailRow({ label, value }) {
  return (
    <div className="py-2 flex items-start justify-between gap-4 border-b border-line last:border-0">
      <span className="text-xs text-ink-faint shrink-0">{label}</span>
      <span className="text-xs font-medium text-ink text-right break-all">{value ?? "—"}</span>
    </div>
  );
}

/** Olay detayı — klip/tespit fotoğrafı sekmeleri, metadata ve lifecycle aksiyonları. */
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
    <Modal open onClose={onClose} title={eventTypeLabel(event.event_type)} wide>
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Badge className={sev.badge}>Risk {event.risk_score} · {sev.label}</Badge>
            <Badge className={st.badge}>{st.label}</Badge>
          </div>
          {/* Medya sekmeleri — hem klip hem tespit fotoğrafı varsa */}
          {hasClip && hasPhoto && (
            <div className="flex rounded-xl bg-slate-100 p-0.5">
              {[
                { id: "clip", label: "Video Klip", icon: Clapperboard },
                { id: "photo", label: "Tespit Fotoğrafı", icon: ImageIcon },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setMediaTab(id)}
                  className={clsx(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-medium transition-colors",
                    activeMedia === id
                      ? "bg-surface text-ink shadow-card"
                      : "text-ink-faint hover:text-ink"
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Video klip / tespit fotoğrafı / boş durum */}
        {activeMedia === "clip" && hasClip ? (
          <video
            src={api.events.clipUrl(event.id)}
            controls
            autoPlay
            muted
            className="w-full rounded-xl border border-line bg-slate-900"
            onError={() => setClipFailed(true)}
          />
        ) : hasPhoto ? (
          <img
            src={api.events.thumbnailUrl(event.id)}
            alt="tespit fotoğrafı"
            className="w-full rounded-xl border border-line"
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-10 bg-slate-50 rounded-xl border border-line text-ink-faint">
            <ImageOff className="w-6 h-6 mb-2" />
            <p className="text-xs">Bu olay için görüntü yok</p>
          </div>
        )}
        {event.clip_path && clipFailed && (
          <p className="text-xs text-amber-600">
            Klip tarayıcıda oynatılamadı —{" "}
            <a
              href={api.events.clipUrl(event.id)}
              download
              className="text-accent font-medium hover:underline inline-flex items-center gap-1"
            >
              <Download className="w-3 h-3" /> indirmek için tıklayın
            </a>
          </p>
        )}

        {/* Detay alanları */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
          <div>
            <DetailRow label="Kamera" value={event.camera_id} />
            <DetailRow label="Başlangıç" value={formatDateTime(event.started_at)} />
            <DetailRow label="Bitiş" value={formatDateTime(event.ended_at)} />
          </div>
          <div>
            <DetailRow label="Bölge" value={event.zone_id} />
            <DetailRow label="Track ID" value={event.track_ids?.join(", ") || "—"} />
            <DetailRow label="Sınıflar" value={event.detected_classes?.join(", ") || "—"} />
          </div>
        </div>

        {event.metadata && Object.keys(event.metadata).length > 0 && (
          <details className="group">
            <summary className="text-xs font-medium text-ink-soft cursor-pointer hover:text-ink">
              Teknik metadata
            </summary>
            <pre className="mt-2 bg-slate-50 border border-line rounded-xl p-3 text-[11px] text-ink-soft overflow-x-auto">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          </details>
        )}

        {/* Lifecycle aksiyonları */}
        {!isTerminal && (
          <div className="flex items-center gap-2 pt-2 border-t border-line">
            <Button
              size="sm"
              onClick={() => statusMutation.mutate({ id: event.id, status: "RESOLVED" })}
              disabled={statusMutation.isPending}
              className="!bg-emerald-600 hover:!bg-emerald-700"
            >
              <CheckCircle2 className="w-4 h-4" /> Çözüldü İşaretle
            </Button>
            {event.status !== "ESCALATED" && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => statusMutation.mutate({ id: event.id, status: "ESCALATED" })}
                disabled={statusMutation.isPending}
              >
                <ArrowUpCircle className="w-4 h-4" /> Yükselt
              </Button>
            )}
            {statusMutation.isError && (
              <span className="text-xs text-rose-600">Güncelleme başarısız</span>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
