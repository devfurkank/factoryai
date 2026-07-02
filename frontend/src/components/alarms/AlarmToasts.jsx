import clsx from "clsx";
import { X, ShieldAlert } from "lucide-react";
import { useAlarms } from "../../context/AlarmContext";
import { eventTypeLabel, SEVERITY_META, formatTime } from "../../lib/format";

const TONE = {
  CRITICAL: "border-l-rose-500",
  HIGH: "border-l-orange-500",
  MEDIUM: "border-l-amber-500",
  LOW: "border-l-slate-400",
};

/** Sağ üstte kayarak beliren alarm bildirimleri — 6 sn sonra otomatik kapanır. */
export default function AlarmToasts() {
  const { toasts, dismissToast } = useAlarms();
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-20 right-4 z-[60] space-y-2 w-80">
      {toasts.map(({ id, alarm }) => {
        const sev = SEVERITY_META[alarm.severity] || SEVERITY_META.LOW;
        return (
          <div
            key={id}
            className={clsx(
              "bg-surface border border-line rounded-xl shadow-pop p-3.5 flex gap-3",
              "border-l-4 animate-slide-in",
              TONE[alarm.severity] || TONE.LOW
            )}
          >
            <div className={clsx("w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
              alarm.severity === "CRITICAL" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600")}>
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-ink truncate">
                {eventTypeLabel(alarm.event_type)}
              </p>
              <p className="text-xs text-ink-faint mt-0.5">
                {alarm.camera_id} · Risk {alarm.risk_score} ({sev.label}) · {formatTime(alarm.timestamp)}
              </p>
            </div>
            <button
              onClick={() => dismissToast(id)}
              className="p-1 rounded-lg text-ink-faint hover:bg-slate-100 self-start"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
