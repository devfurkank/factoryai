"""
Alarm Sistemi — Faz 5 (Gün 18).

Olay üretildiğinde üç kanala bildirim gönderir:
1. WebSocket — /ws/alarms bağlantılarına ALARM payload'ı (web panel canlı liste)
2. Webhook — ALARM_WEBHOOK_URL tanımlıysa HTTP POST (harici sistemler)
3. Telegram — TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID tanımlıysa mesaj

WebSocket broadcast await edilir (panelin olay anında görmesi kritik);
webhook/Telegram fire-and-forget background task olarak gönderilir — dış
servis yavaşlığı/hatası olay işleme hattını asla bloklamaz veya düşürmez.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Set

import httpx
import structlog
from fastapi import WebSocket

from app.config import settings
from app.events.schemas import EventCreate

log = structlog.get_logger()

_WEBHOOK_TIMEOUT = 5.0
_TELEGRAM_TIMEOUT = 10.0

# Telegram mesajındaki önem ikonu
_SEVERITY_ICONS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "⚪",
}


def build_alarm_payload(
    event_id: str,
    event: EventCreate,
    thumbnail_path: Optional[str] = None,
) -> dict:
    """Roadmap §5.8 ALARM şeması — frontend AlarmPanel bu alanları bekler."""
    return {
        "type": "ALARM",
        "event_id": event_id,
        "event_type": event.event_type.value,
        "severity": event.severity.value,
        "risk_score": event.risk_score,
        "camera_id": event.camera_id,
        "zone_id": event.zone_id,
        "detected_classes": event.detected_classes,
        "timestamp": event.started_at.isoformat(),
        # Dosya sistemi path'i yerine URL — tarayıcı doğrudan gösterebilir
        "thumbnail": (
            f"/api/events/{event_id}/thumbnail" if thumbnail_path else None
        ),
    }


class AlarmManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._sent_count = 0
        # Fire-and-forget task referansları (GC koruması)
        self._tasks: Set[asyncio.Task] = set()

    # ── WebSocket Bağlantı Havuzu ──────────────────────────────────────────────
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

    # ── Olay Bildirimi (tüm kanallar) ──────────────────────────────────────────
    async def notify_event(
        self,
        event_id: str,
        event: EventCreate,
        thumbnail_path: Optional[str] = None,
    ):
        """EventEngine olay yazdıktan sonra çağırır: WebSocket'e anında yayınlar,
        webhook/Telegram'ı arka planda gönderir. Hiçbir kanal hatası yukarı
        yayılmaz — alarm gönderilemiyor olması olay üretimini durdurmamalı."""
        payload = build_alarm_payload(event_id, event, thumbnail_path)

        try:
            await self.broadcast(payload)
        except Exception as exc:
            log.warning("alarm.ws.broadcast_failed", event_id=event_id, error=str(exc))

        if settings.alarm_webhook_url:
            self._spawn(self._send_webhook(payload), f"webhook-{event_id}")
        if settings.telegram_bot_token and settings.telegram_chat_id:
            self._spawn(self._send_telegram(payload), f"telegram-{event_id}")

        self._sent_count += 1
        log.info(
            "alarm.sent",
            event_id=event_id,
            event_type=payload["event_type"],
            severity=payload["severity"],
            ws_connections=self.connection_count,
            webhook=bool(settings.alarm_webhook_url),
            telegram=bool(settings.telegram_bot_token and settings.telegram_chat_id),
        )

    def _spawn(self, coro, name: str):
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # ── Webhook Kanalı ─────────────────────────────────────────────────────────
    async def _send_webhook(self, payload: dict):
        try:
            async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
                resp = await client.post(settings.alarm_webhook_url, json=payload)
                if resp.status_code >= 400:
                    log.warning(
                        "alarm.webhook.rejected",
                        status=resp.status_code,
                        event_id=payload["event_id"],
                    )
        except Exception as exc:
            log.warning(
                "alarm.webhook.failed",
                event_id=payload["event_id"],
                error=str(exc),
            )

    # ── Telegram Kanalı ────────────────────────────────────────────────────────
    async def _send_telegram(self, payload: dict):
        icon = _SEVERITY_ICONS.get(payload["severity"], "⚪")
        text = (
            f"{icon} *{payload['event_type'].replace('_', ' ')}*\n"
            f"Kamera: `{payload['camera_id']}`\n"
            f"Risk: {payload['risk_score']} ({payload['severity']})\n"
            f"Zaman: {payload['timestamp']}"
        )
        if payload.get("zone_id"):
            text += f"\nBölge: `{payload['zone_id']}`"

        url = (
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        )
        try:
            async with httpx.AsyncClient(timeout=_TELEGRAM_TIMEOUT) as client:
                resp = await client.post(url, json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                if resp.status_code >= 400:
                    log.warning(
                        "alarm.telegram.rejected",
                        status=resp.status_code,
                        event_id=payload["event_id"],
                    )
        except Exception as exc:
            log.warning(
                "alarm.telegram.failed",
                event_id=payload["event_id"],
                error=str(exc),
            )

    def get_stats(self) -> dict:
        return {
            "ws_connections": self.connection_count,
            "alarms_sent": self._sent_count,
            "webhook_enabled": bool(settings.alarm_webhook_url),
            "telegram_enabled": bool(
                settings.telegram_bot_token and settings.telegram_chat_id
            ),
        }


alarm_manager = AlarmManager()
