const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
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
  },
  events: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return request(`/api/events${q ? "?" + q : ""}`);
    },
    get: (id) => request(`/api/events/${id}`),
    dailyStats: () => request("/api/events/stats/daily"),
  },
};
