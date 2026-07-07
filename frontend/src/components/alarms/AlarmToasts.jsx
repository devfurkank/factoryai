import clsx from "clsx";
import { useAlarms } from "../../context/AlarmContext";
import Icon from "../Icon";
import { eventTypeLabel, SEVERITY_META, formatTime } from "../../lib/format";

const TONE = {
  CRITICAL: "border-l-error",
  HIGH: "border-l-tertiary",
  MEDIUM: "border-l-primary",
  LOW: "border-l-outline",
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
              "glass-panel-elevated rounded-xl p-3.5 flex gap-3",
              "border-l-4 animate-slide-in",
              TONE[alarm.severity] || TONE.LOW
            )}
          >
            <div
              className={clsx(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                alarm.severity === "CRITICAL" ? "bg-error/20 text-error" : "bg-tertiary/20 text-tertiary"
              )}
            >
              <Icon name="warning" className="text-base" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-on-surface truncate">
                {eventTypeLabel(alarm.event_type)}
              </p>
              <p className="text-xs text-on-surface-variant mt-0.5">
                {alarm.camera_id} · Risk {alarm.risk_score} ({sev.label}) · {formatTime(alarm.timestamp)}
              </p>
            </div>
            <button
              onClick={() => dismissToast(id)}
              className="p-1 rounded-lg text-on-surface-variant hover:bg-primary/10 hover:text-on-surface self-start"
            >
              <Icon name="close" className="text-base" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
