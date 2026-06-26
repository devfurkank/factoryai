"""
Alarm Yöneticisi — Faz 5 (Gün 18) kapsamında tam implement edilecek.
Şu an WebSocket bağlantı havuzunu tutar.
"""
from __future__ import annotations
import asyncio
import structlog
from fastapi import WebSocket

log = structlog.get_logger()


class AlarmManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        log.info("alarm.ws.connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        log.info("alarm.ws.disconnected", total=len(self._connections))

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


alarm_manager = AlarmManager()
