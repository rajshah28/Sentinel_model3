"""
WebSocket endpoint that streams alerts to the dashboard in real time as
they're published on the event bus by the correlation engine -- so a
watchlist match appears in the UI within seconds, over the same
federation bus the rest of the system uses (not a separate polling hack).
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bus.event_bus import Topics, bus

logger = logging.getLogger("sentinel.ws")
router = APIRouter()


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    queue = bus.subscribe_now(Topics.ALERTS)
    try:
        async for alert in bus.drain(Topics.ALERTS, queue):
            await websocket.send_json(alert.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.info("ws client disconnected")
