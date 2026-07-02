import clsx from "clsx";
import { Loader2, Inbox, X } from "lucide-react";

/** Küçük UI primitifleri — Faz 6 açık tema tasarım sistemi. */

export function Card({ className, children, ...props }) {
  return (
    <div
      className={clsx(
        "bg-surface border border-line rounded-2xl shadow-card",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between px-5 pt-4 pb-1">
      <div>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && <p className="text-xs text-ink-faint mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ className, children }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ring-1 ring-inset",
        className
      )}
    >
      {children}
    </span>
  );
}

export function Button({ variant = "primary", size = "md", className, children, ...props }) {
  const variants = {
    primary: "bg-accent text-white hover:bg-accent-strong shadow-sm",
    secondary: "bg-surface text-ink-soft border border-line hover:bg-slate-50 hover:text-ink",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
    ghost: "text-ink-soft hover:bg-slate-100 hover:text-ink",
  };
  const sizes = {
    sm: "px-2.5 py-1.5 text-xs rounded-lg",
    md: "px-3.5 py-2 text-sm rounded-xl",
  };
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 font-medium transition-colors",
        "disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Select({ className, children, ...props }) {
  return (
    <select
      className={clsx(
        "bg-surface border border-line rounded-xl px-3 py-2 text-sm text-ink-soft",
        "focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Input({ className, ...props }) {
  return (
    <input
      className={clsx(
        "bg-surface border border-line rounded-xl px-3 py-2 text-sm text-ink",
        "placeholder:text-ink-faint",
        "focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent",
        className
      )}
      {...props}
    />
  );
}

export function Spinner({ className }) {
  return <Loader2 className={clsx("animate-spin text-accent", className || "w-5 h-5")} />;
}

export function EmptyState({ icon: Icon = Inbox, title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-3">
        <Icon className="w-6 h-6 text-ink-faint" />
      </div>
      <p className="text-sm font-medium text-ink-soft">{title}</p>
      {hint && <p className="text-xs text-ink-faint mt-1 max-w-xs">{hint}</p>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide = false }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[2px] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className={clsx(
          "bg-surface rounded-2xl shadow-pop w-full max-h-[90vh] overflow-y-auto animate-fade-up",
          wide ? "max-w-3xl" : "max-w-xl"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-line sticky top-0 bg-surface rounded-t-2xl z-10">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-ink-faint hover:bg-slate-100 hover:text-ink transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

/** KPI kartı — dashboard üst sırası. */
export function StatCard({ icon: Icon, label, value, sub, tone = "indigo" }) {
  const tones = {
    indigo: "bg-accent-soft text-accent",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
    sky: "bg-sky-50 text-sky-600",
  };
  return (
    <Card className="p-5 flex items-start gap-4">
      <div className={clsx("w-11 h-11 rounded-xl flex items-center justify-center shrink-0", tones[tone])}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-ink-faint">{label}</p>
        <p className="text-2xl font-bold text-ink mt-0.5 tabular-nums">{value ?? "—"}</p>
        {sub && <p className="text-xs text-ink-faint mt-0.5 truncate">{sub}</p>}
      </div>
    </Card>
  );
}
