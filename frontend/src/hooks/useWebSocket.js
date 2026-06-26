import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${location.host}`;

export function useWebSocket(path) {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    ws.current = new WebSocket(`${WS_BASE}${path}`);

    ws.current.onopen = () => setConnected(true);
    ws.current.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000); // otomatik yeniden bağlan
    };
    ws.current.onerror = () => ws.current?.close();
    ws.current.onmessage = (e) => {
      try {
        setLastMessage(JSON.parse(e.data));
      } catch {
        setLastMessage(e.data);
      }
    };

    // Ping - bağlantıyı canlı tut
    const ping = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send("ping");
      }
    }, 25000);

    ws.current._ping = ping;
  }, [path]);

  useEffect(() => {
    connect();
    return () => {
      clearInterval(ws.current?._ping);
      ws.current?.close();
    };
  }, [connect]);

  return { connected, lastMessage };
}
