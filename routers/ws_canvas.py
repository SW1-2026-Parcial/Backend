"""
WebSocket /ws/canvas/{versionId} — canvas colaborativo con presencia.
Requiere JWT como query param: ?token=<jwt>

Eventos recibidos del cliente (JSON):
  { "tipo": "NODE_MOVED",      "nodoId": "...", "posicion": {...} }
  { "tipo": "NODE_CREATED",    "nodo": {...} }
  { "tipo": "NODE_DELETED",    "nodoId": "..." }
  { "tipo": "CONNECTION_CREATED", "origen": "...", "destino": "..." }
  { "tipo": "PING" }

Eventos emitidos a todos los presentes:
  { "tipo": "PRESENCE_UPDATE", "usuarios": [...] }
  { "tipo": "NODE_MOVED", ... }   ← rebroadcast del evento original
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from core.security import decode_token
from core.websocket_manager import ws_manager
from services.canvas.canvas_session_manager import canvas_session_manager
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket-canvas"])


@router.websocket("/ws/canvas/{version_id}")
async def canvas_ws(
    websocket: WebSocket,
    version_id: str,
    token: str = Query(..., description="JWT del usuario"),
):
    # Validar JWT
    try:
        payload = decode_token(token)
        email: str = payload["sub"]
        user = await User.find_one(User.email == email, User.activo == True)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    topic = f"canvas/{version_id}"
    user_id = str(user.id)

    # Conectar al WS manager y registrar presencia
    await ws_manager.connect(topic, websocket)
    presence_info = await canvas_session_manager.join(version_id, user_id, user.nombre)

    # Notificar a todos la presencia actualizada
    await _broadcast_presence(version_id, topic)
    logger.info("[canvas_ws] %s entró al canvas %s", user.nombre, version_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            tipo = event.get("tipo", "")

            if tipo == "PING":
                await canvas_session_manager.ping(version_id, user_id)
                await websocket.send_text(json.dumps({"tipo": "PONG"}))
                continue

            # Enriquecer el evento con el autor y hacer rebroadcast
            event["userId"] = user_id
            event["userName"] = user.nombre
            event["color"] = presence_info.color
            await ws_manager.broadcast(topic, event)

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(topic, websocket)
        await canvas_session_manager.leave(version_id, user_id)
        await _broadcast_presence(version_id, topic)
        logger.info("[canvas_ws] %s salió del canvas %s", user.nombre, version_id)


async def _broadcast_presence(version_id: str, topic: str) -> None:
    usuarios = await canvas_session_manager.get_presence(version_id)
    await ws_manager.broadcast(topic, {
        "tipo": "PRESENCE_UPDATE",
        "usuarios": usuarios,
    })
