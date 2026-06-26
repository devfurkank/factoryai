from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.alarm.manager import alarm_manager
import structlog

log = structlog.get_logger()
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alarms")
async def alarm_ws(ws: WebSocket):
    await alarm_manager.connect(ws)
    try:
        while True:
            # Ping mesajı bekle (bağlantı canlı tut)
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        alarm_manager.disconnect(ws)
