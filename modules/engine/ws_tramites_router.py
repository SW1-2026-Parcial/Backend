"""
WebSocket /ws/tramites/{tramiteId} — estado del trámite en tiempo real.
Público (sin auth) — usado por la app Flutter para seguimiento de tickets.

El cliente solo recibe mensajes; no envía nada excepto PING.
Los broadcasts los emite el EventBus listener (ws_broadcaster.py).
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket_manager import ws_manager
from models.tramite import Tramite

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket-tramites"])


@router.websocket("/ws/tramites/{tramite_id}")
async def tramite_ws(websocket: WebSocket, tramite_id: str):
    topic = f"tramites/{tramite_id}"
    await ws_manager.connect(topic, websocket)
    logger.debug("[tramite_ws] cliente conectado a %s", topic)

    # Enviar estado actual al conectar
    tramite = await _find_tramite_by_id(tramite_id)
    if tramite:
        await websocket.send_text(json.dumps({
            "type": "TRAMITE_STATUS",
            "tramiteId": str(tramite.id),
            "ticketNumber": tramite.ticketNumber,
            "status": tramite.status.value,
            "currentNodeIds": tramite.currentNodeIds,
        }))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("tipo") == "PING":
                    await websocket.send_text(json.dumps({"tipo": "PONG"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(topic, websocket)
        logger.debug("[tramite_ws] cliente desconectado de %s", topic)


async def _find_tramite_by_id(tramite_id: str):
    try:
        from beanie import PydanticObjectId
        return await Tramite.get(PydanticObjectId(tramite_id))
    except Exception:
        return None
