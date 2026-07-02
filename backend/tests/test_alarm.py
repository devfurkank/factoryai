"""Alarm sistemi testleri — Faz 5 (Gün 18: payload, broadcast, kanallar)."""
import asyncio
from datetime import datetime, timezone

import pytest

from app.alarm.manager import AlarmManager, build_alarm_payload
from app.config import settings
from app.events.schemas import EventCreate, EventType, Severity


def _event(**overrides):
    defaults = dict(
        camera_id="cam_01",
        event_type=EventType.FIRE,
        severity=Severity.CRITICAL,
        risk_score=100,
        started_at=datetime(2026, 7, 2, 10, 30, tzinfo=timezone.utc),
        zone_id="zone_a",
        track_ids=[7],
        detected_classes=["fire_smoke"],
        metadata={"confidence": 0.92},
    )
    defaults.update(overrides)
    return EventCreate(**defaults)


class FakeWebSocket:
    """send_json çağrılarını kaydeden sahte WebSocket."""

    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        if self.fail:
            raise RuntimeError("bağlantı koptu")
        self.sent.append(payload)


# ── Payload Şeması (Roadmap §5.8) ─────────────────────────────────────────────
class TestAlarmPayload:
    def test_contains_roadmap_fields(self):
        payload = build_alarm_payload("ev-1", _event(), thumbnail_path="/x/ev-1.jpg")
        assert payload["type"] == "ALARM"
        assert payload["event_id"] == "ev-1"
        assert payload["event_type"] == "FIRE"
        assert payload["severity"] == "CRITICAL"
        assert payload["risk_score"] == 100
        assert payload["camera_id"] == "cam_01"
        assert payload["zone_id"] == "zone_a"
        assert payload["timestamp"] == "2026-07-02T10:30:00+00:00"

    def test_thumbnail_is_url_not_fs_path(self):
        """Frontend'in doğrudan gösterebilmesi için dosya sistemi path'i değil
        API URL'i gönderilmeli."""
        payload = build_alarm_payload("ev-1", _event(), thumbnail_path="/app/thumbnails/ev-1.jpg")
        assert payload["thumbnail"] == "/api/events/ev-1/thumbnail"

    def test_no_thumbnail_is_none(self):
        payload = build_alarm_payload("ev-1", _event(), thumbnail_path=None)
        assert payload["thumbnail"] is None

    def test_payload_json_serializable(self):
        import json
        payload = build_alarm_payload("ev-1", _event())
        json.dumps(payload)  # exception fırlatmamalı


# ── WebSocket Broadcast ───────────────────────────────────────────────────────
class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self):
        mgr = AlarmManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await mgr.connect(ws1)
        await mgr.connect(ws2)
        assert ws1.accepted and ws2.accepted
        assert mgr.connection_count == 2

        await mgr.broadcast({"type": "ALARM", "x": 1})
        assert ws1.sent == [{"type": "ALARM", "x": 1}]
        assert ws2.sent == [{"type": "ALARM", "x": 1}]

    @pytest.mark.asyncio
    async def test_dead_connection_removed(self):
        mgr = AlarmManager()
        ok_ws, dead_ws = FakeWebSocket(), FakeWebSocket(fail=True)
        await mgr.connect(ok_ws)
        await mgr.connect(dead_ws)

        await mgr.broadcast({"a": 1})
        assert mgr.connection_count == 1
        assert ok_ws.sent == [{"a": 1}]

        # Ölü bağlantı çıkarıldıktan sonra ikinci broadcast sorunsuz
        await mgr.broadcast({"a": 2})
        assert ok_ws.sent == [{"a": 1}, {"a": 2}]

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self):
        mgr = AlarmManager()
        ws = FakeWebSocket()
        await mgr.connect(ws)
        mgr.disconnect(ws)
        mgr.disconnect(ws)  # ikinci çağrı hata fırlatmamalı
        assert mgr.connection_count == 0


# ── notify_event (tüm kanallar) ───────────────────────────────────────────────
class TestNotifyEvent:
    @pytest.mark.asyncio
    async def test_ws_receives_alarm(self, monkeypatch):
        monkeypatch.setattr(settings, "alarm_webhook_url", "")
        monkeypatch.setattr(settings, "telegram_bot_token", "")
        mgr = AlarmManager()
        ws = FakeWebSocket()
        await mgr.connect(ws)

        await mgr.notify_event("ev-1", _event(), thumbnail_path="/t/ev-1.jpg")
        assert len(ws.sent) == 1
        assert ws.sent[0]["type"] == "ALARM"
        assert ws.sent[0]["event_id"] == "ev-1"
        assert mgr.get_stats()["alarms_sent"] == 1

    @pytest.mark.asyncio
    async def test_no_connections_no_error(self, monkeypatch):
        monkeypatch.setattr(settings, "alarm_webhook_url", "")
        monkeypatch.setattr(settings, "telegram_bot_token", "")
        mgr = AlarmManager()
        await mgr.notify_event("ev-1", _event())  # exception fırlatmamalı
        assert mgr.get_stats()["alarms_sent"] == 1

    @pytest.mark.asyncio
    async def test_webhook_spawned_when_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "alarm_webhook_url", "http://example.local/hook")
        monkeypatch.setattr(settings, "telegram_bot_token", "")
        mgr = AlarmManager()

        called = {}

        async def fake_webhook(payload):
            called["payload"] = payload

        monkeypatch.setattr(mgr, "_send_webhook", fake_webhook)
        await mgr.notify_event("ev-1", _event())
        # Fire-and-forget task'in çalışmasına izin ver
        await asyncio.sleep(0)
        assert called["payload"]["event_id"] == "ev-1"

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_propagate(self, monkeypatch):
        """Erişilemeyen webhook URL'i notify_event'i düşürmemeli."""
        monkeypatch.setattr(settings, "alarm_webhook_url", "http://127.0.0.1:1/yok")
        monkeypatch.setattr(settings, "telegram_bot_token", "")
        mgr = AlarmManager()
        await mgr.notify_event("ev-1", _event())
        # Background task'in hatayı yutmasını bekle
        await asyncio.sleep(0.2)
        assert mgr.get_stats()["alarms_sent"] == 1

    @pytest.mark.asyncio
    async def test_telegram_requires_both_token_and_chat_id(self, monkeypatch):
        monkeypatch.setattr(settings, "alarm_webhook_url", "")
        monkeypatch.setattr(settings, "telegram_bot_token", "token-var")
        monkeypatch.setattr(settings, "telegram_chat_id", "")  # chat_id yok
        mgr = AlarmManager()

        called = {}

        async def fake_telegram(payload):
            called["payload"] = payload

        monkeypatch.setattr(mgr, "_send_telegram", fake_telegram)
        await mgr.notify_event("ev-1", _event())
        await asyncio.sleep(0)
        assert called == {}  # chat_id olmadan gönderilmemeli

    def test_stats_reflect_channel_config(self, monkeypatch):
        monkeypatch.setattr(settings, "alarm_webhook_url", "http://x")
        monkeypatch.setattr(settings, "telegram_bot_token", "t")
        monkeypatch.setattr(settings, "telegram_chat_id", "c")
        mgr = AlarmManager()
        stats = mgr.get_stats()
        assert stats["webhook_enabled"] is True
        assert stats["telegram_enabled"] is True
