"""
WebSocket /ws/tareas/{departamento_id} — notificaciones push de tareas nuevas.
Requiere JWT: ?token=<jwt>

Los funcionarios se suscriben a su departamento para recibir alertas
cuando se crea una nueva tarea que pueden tomar.
También sirve para alertas generales del supervisor (/ws/tareas/alertas).
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from core.security import decode_token
from core.websocket_manager import ws_manager
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket-tareas"])


@router.websocket("/ws/tareas/{departamento_id}")
async def tareas_ws(
    websocket: WebSocket,
    departamento_id: str,
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

    topic = f"tareas/{departamento_id}"
    await ws_manager.connect(topic, websocket)
    logger.debug("[tareas_ws] %s conectado a %s", user.nombre, topic)

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
        logger.debug("[tareas_ws] %s desconectado de %s", user.nombre, topic)
