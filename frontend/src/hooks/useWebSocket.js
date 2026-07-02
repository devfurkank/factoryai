import { useEffect, useRef, useState } from "react";

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${location.host}`;

export function useWebSocket(path) {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  useEffect(() => {
    // Tüm zamanlayıcılar bu effect kapsamında tutulur ve cleanup'ta topluca
    // temizlenir — önceki implementasyon her reconnect'te yeni bir ping
    // interval'i yaratıyor ve yalnızca sonuncusunu temizliyordu (leak);
    // unmount sonrası reconnect setTimeout'u da çalışmaya devam ediyordu.
    let disposed = false;
    let reconnectTimer = null;
    let pingTimer = null;

    const connect = () => {
      if (disposed) return;
      const socket = new WebSocket(`${WS_BASE}${path}`);
      ws.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        clearInterval(pingTimer);
        if (!disposed) reconnectTimer = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket.close();
      socket.onmessage = (e) => {
        try {
          setLastMessage(JSON.parse(e.data));
        } catch {
          setLastMessage(e.data);
        }
      };

      // Ping - bağlantıyı canlı tut
      pingTimer = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send("ping");
      }, 25000);
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      clearInterval(pingTimer);
      ws.current?.close();
    };
  }, [path]);

  return { connected, lastMessage };
}
