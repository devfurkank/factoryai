/** Ortak etiketler ve biçimlendirme — Faz 6 tasarım sistemi. */

export const EVENT_TYPE_LABELS = {
  FORBIDDEN_ZONE_ENTRY: "Yasak Bölge İhlali",
  PPE_VIOLATION: "KKD İhlali",
  FALL: "Düşme",
  INACTIVITY: "Hareketsizlik",
  FIRE: "Yangın / Alev",
  SMOKE: "Duman",
  FORKLIFT_PROXIMITY: "Forklift Yakınlığı",
  DIRECTION_VIOLATION: "Ters Yön",
};

export const EVENT_TYPES = Object.keys(EVENT_TYPE_LABELS);

export function eventTypeLabel(type) {
  return EVENT_TYPE_LABELS[type] || (type || "").replace(/_/g, " ");
}

/** Önem seviyesi görsel meta'sı — Glacier koyu tema rozet/nokta renkleri. */
export const SEVERITY_META = {
  CRITICAL: { label: "Kritik", badge: "bg-error/20 text-error border-error/30", dot: "bg-error" },
  HIGH:     { label: "Yüksek", badge: "bg-tertiary/20 text-tertiary border-tertiary/30", dot: "bg-tertiary" },
  MEDIUM:   { label: "Orta", badge: "bg-primary/20 text-primary border-primary/30", dot: "bg-primary" },
  LOW:      { label: "Düşük", badge: "bg-surface-container text-on-surface-variant border-outline-variant/30", dot: "bg-outline" },
};

export const SEVERITIES = Object.keys(SEVERITY_META);

export const STATUS_META = {
  PENDING:   { label: "Beklemede", badge: "bg-secondary/10 text-secondary-fixed-dim border-secondary/20" },
  ACTIVE:    { label: "Aktif", badge: "bg-secondary/20 text-secondary border-secondary/30" },
  SUSTAINED: { label: "Sürüyor", badge: "bg-surface-container-high text-on-surface-variant border-outline-variant/50" },
  RESOLVED:  { label: "Çözüldü", badge: "bg-primary-container text-primary-fixed border-primary/20" },
  ESCALATED: { label: "Yükseltildi", badge: "bg-error/20 text-error border-error/30" },
};

export function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("tr-TR", {
    day: "2-digit", month: "long", year: "numeric",
  });
}

/** Kısa göreli zaman: "az önce", "5 dk", "2 sa", "3 gün". */
export function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "az önce";
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

/** Grafiklerde kullanılan seri renkleri (Glacier koyu tema paleti). */
export const CHART_COLORS = [
  "#7dd3fc", "#ff6b6b", "#c8a0f0", "#88b4cc",
  "#ffb3b3", "#4a6070", "#c8eaff", "#3d2060",
];
