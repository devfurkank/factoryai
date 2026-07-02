const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    // FastAPI hata gövdesindeki detail alanını kullanıcıya taşı
    let detail = "";
    try {
      detail = (await res.json())?.detail || "";
    } catch { /* gövde JSON değilse yoksay */ }
    throw new Error(detail || `API ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  cameras: {
    list: () => request("/api/cameras"),
    get: (id) => request(`/api/cameras/${id}`),
    status: (id) => request(`/api/cameras/${id}/status`),
    allStatus: () => request("/api/cameras/all/status"),
    add: (body) => request("/api/cameras", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) =>
      request(`/api/cameras/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    events: (id, params = {}) => {
      const q = new URLSearchParams(params).toString();
      return request(`/api/cameras/${id}/events${q ? "?" + q : ""}`);
    },
  },
  events: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return request(`/api/events${q ? "?" + q : ""}`);
    },
    get: (id) => request(`/api/events/${id}`),
    dailyStats: () => request("/api/events/stats/daily"),
    hourlyStats: () => request("/api/events/stats/hourly"),
    rangeStats: (days = 7) => request(`/api/events/stats/range?days=${days}`),
    updateStatus: (id, status) =>
      request(`/api/events/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    thumbnailUrl: (id) => `${BASE}/api/events/${id}/thumbnail`,
    clipUrl: (id) => `${BASE}/api/events/${id}/clip`,
  },
  // Faz 6 — Raporlama ve Soru-Cevap
  summary: {
    list: (limit = 30) => request(`/api/summary?limit=${limit}`),
    daily: (date) => request(`/api/summary/daily/${date}`),
    generate: (date, force = false) =>
      request("/api/summary/generate", {
        method: "POST",
        body: JSON.stringify({ date, force }),
      }),
  },
  assistant: {
    query: (question) =>
      request("/api/query", { method: "POST", body: JSON.stringify({ question }) }),
    status: () => request("/api/assistant/status"),
  },
  streams: {
    list: () => request("/api/streams"),
  },
};
