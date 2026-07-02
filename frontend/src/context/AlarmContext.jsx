import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket } from "../hooks/useWebSocket";

/**
 * Global alarm durumu — Faz 6.
 * Tek WebSocket bağlantısı (/ws/alarms) uygulama genelinde paylaşılır:
 * topbar'daki zil, toast bildirimleri ve sayfalardaki canlı listeler
 * hepsi bu context'ten beslenir.
 */
const AlarmContext = createContext(null);

let toastSeq = 0;

export function AlarmProvider({ children }) {
  const { connected, lastMessage } = useWebSocket("/ws/alarms");
  const [alarms, setAlarms] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [unread, setUnread] = useState(0);
  const queryClient = useQueryClient();
  const timersRef = useRef(new Map());

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  useEffect(() => {
    if (!lastMessage || lastMessage === "pong") return;

    if (lastMessage.type === "ALARM") {
      setAlarms((prev) => [lastMessage, ...prev].slice(0, 100));
      setUnread((n) => n + 1);
      // Yeni olay geldi — olay listeleri ve istatistikler tazelensin
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["events-daily-stats"] });

      const id = ++toastSeq;
      setToasts((prev) => [{ id, alarm: lastMessage }, ...prev].slice(0, 4));
      timersRef.current.set(id, setTimeout(() => dismissToast(id), 6000));
    }

    if (lastMessage.type === "CLIP_READY") {
      setAlarms((prev) =>
        prev.map((a) =>
          a.event_id === lastMessage.event_id ? { ...a, clip_url: lastMessage.clip_url } : a
        )
      );
    }
  }, [lastMessage, dismissToast, queryClient]);

  // Unmount'ta bekleyen toast zamanlayıcılarını temizle
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
      timers.clear();
    };
  }, []);

  const markRead = useCallback(() => setUnread(0), []);

  const value = useMemo(
    () => ({ connected, alarms, toasts, unread, markRead, dismissToast }),
    [connected, alarms, toasts, unread, markRead, dismissToast]
  );

  return <AlarmContext.Provider value={value}>{children}</AlarmContext.Provider>;
}

export function useAlarms() {
  const ctx = useContext(AlarmContext);
  if (!ctx) throw new Error("useAlarms, AlarmProvider içinde kullanılmalı");
  return ctx;
}
