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

/** Önem seviyesi görsel meta'sı — açık tema rozet/nokta renkleri. */
export const SEVERITY_META = {
  CRITICAL: { label: "Kritik", badge: "bg-rose-50 text-rose-700 ring-rose-200", dot: "bg-rose-500" },
  HIGH:     { label: "Yüksek", badge: "bg-orange-50 text-orange-700 ring-orange-200", dot: "bg-orange-500" },
  MEDIUM:   { label: "Orta", badge: "bg-amber-50 text-amber-700 ring-amber-200", dot: "bg-amber-500" },
  LOW:      { label: "Düşük", badge: "bg-slate-100 text-slate-600 ring-slate-200", dot: "bg-slate-400" },
};

export const SEVERITIES = Object.keys(SEVERITY_META);

export const STATUS_META = {
  PENDING:   { label: "Beklemede", badge: "bg-slate-100 text-slate-600 ring-slate-200" },
  ACTIVE:    { label: "Aktif", badge: "bg-rose-50 text-rose-700 ring-rose-200" },
  SUSTAINED: { label: "Sürüyor", badge: "bg-orange-50 text-orange-700 ring-orange-200" },
  RESOLVED:  { label: "Çözüldü", badge: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  ESCALATED: { label: "Yükseltildi", badge: "bg-violet-50 text-violet-700 ring-violet-200" },
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

/** Grafiklerde kullanılan seri renkleri (açık tema paleti). */
export const CHART_COLORS = [
  "#4f46e5", "#0ea5e9", "#f59e0b", "#f43f5e",
  "#10b981", "#8b5cf6", "#64748b", "#ec4899",
];
