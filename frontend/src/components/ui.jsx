import clsx from "clsx";
import Icon from "./Icon";

/** Küçük UI primitifleri — Glacier glassmorphism koyu tema tasarım sistemi. */

export function Card({ className, children, ...props }) {
  return (
    <div
      className={clsx("glass-panel rounded-xl shadow-glow", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, icon }) {
  return (
    <div className="flex items-start justify-between px-5 pt-4 pb-1">
      <div>
        <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
          {icon && <Icon name={icon} className="text-primary text-[18px]" />}
          {title}
        </h3>
        {subtitle && <p className="text-xs text-on-surface-variant mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ className, children }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border",
        className
      )}
    >
      {children}
    </span>
  );
}

export function Button({ variant = "primary", size = "md", className, children, ...props }) {
  const variants = {
    primary: "bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30",
    secondary: "bg-surface/50 text-on-surface-variant border border-outline-variant hover:bg-surface-variant hover:text-on-surface",
    danger: "bg-error/20 text-error border border-error/30 hover:bg-error/30",
    ghost: "text-on-surface-variant hover:bg-primary/5 hover:text-primary border border-transparent",
  };
  const sizes = {
    sm: "px-2.5 py-1.5 text-xs rounded-lg",
    md: "px-3.5 py-2 text-sm rounded-lg",
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
        "glass-input rounded-lg px-3 py-2 text-sm appearance-none",
        "focus:outline-none",
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
        "glass-input rounded-lg px-3 py-2 text-sm",
        "placeholder:text-on-surface-variant/50",
        "focus:outline-none",
        className
      )}
      {...props}
    />
  );
}

export function Spinner({ className }) {
  return (
    <Icon
      name="progress_activity"
      className={clsx("animate-spin text-primary", className || "text-xl")}
    />
  );
}

export function EmptyState({ icon = "inbox", title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-2xl bg-surface-container-high flex items-center justify-center mb-3 border border-outline-variant/30">
        <Icon name={icon} className="text-on-surface-variant text-2xl" />
      </div>
      <p className="text-sm font-medium text-on-surface-variant">{title}</p>
      {hint && <p className="text-xs text-on-surface-variant/70 mt-1 max-w-xs">{hint}</p>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide = false }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className={clsx(
          "glass-panel-elevated rounded-xl shadow-pop w-full max-h-[90vh] overflow-y-auto animate-fade-up",
          wide ? "max-w-3xl" : "max-w-xl"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-primary/10 sticky top-0 bg-surface/80 backdrop-blur-xl rounded-t-xl z-10">
          <h3 className="text-sm font-semibold text-on-surface">{title}</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-on-surface-variant hover:bg-error/10 hover:text-error transition-colors"
          >
            <Icon name="close" className="text-lg" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

/** KPI kartı — dashboard üst sırası (bento stil, glow arka plan). */
export function StatCard({ icon, label, value, sub, tone = "primary" }) {
  const tones = {
    primary: { text: "text-primary", glow: "bg-primary/5 group-hover:bg-primary/10" },
    error: { text: "text-error", glow: "bg-error/5 group-hover:bg-error/10" },
    tertiary: { text: "text-tertiary", glow: "bg-tertiary/5 group-hover:bg-tertiary/10" },
    secondary: { text: "text-secondary", glow: "bg-secondary/5 group-hover:bg-secondary/10" },
  };
  const t = tones[tone] || tones.primary;
  return (
    <Card className="p-5 flex flex-col gap-2 relative overflow-hidden group">
      <div className={clsx("absolute -right-6 -top-6 w-24 h-24 rounded-full blur-xl transition-colors", t.glow)} />
      <div className="flex items-center justify-between z-10">
        <span className="text-on-surface-variant text-sm font-medium">{label}</span>
        {icon && <Icon name={icon} className={clsx(t.text, "opacity-70")} />}
      </div>
      <div className={clsx("text-3xl font-bold z-10", tone === "error" ? "text-error" : "text-on-surface")}>
        {value ?? "—"}
      </div>
      {sub && <div className={clsx("text-xs mt-auto z-10", t.text)}>{sub}</div>}
    </Card>
  );
}
