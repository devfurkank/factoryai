import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function useEvents(filters = {}) {
  return useQuery({
    queryKey: ["events", filters],
    queryFn: () => api.events.list(filters),
    refetchInterval: 10000,
    keepPreviousData: true,
  });
}

export function useDailyStats() {
  return useQuery({
    queryKey: ["events-daily-stats"],
    queryFn: api.events.dailyStats,
    refetchInterval: 60000,
  });
}
