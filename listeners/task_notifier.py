"""
Listener: notifica al funcionario del departamento cuando se crea una nueva tarea.
Broadcast al topic tareas/{departamentoId} para que los funcionarios la vean en su bandeja.
"""
import logging
from datetime import datetime, timezone

from core.event_bus import event_bus
from core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


@event_bus.on("task_created")
async def _notify_task_available(payload: dict) -> None:
    departamento_id = payload.get("departamento_id")
    topic = f"tareas/{departamento_id}" if departamento_id else "tareas/sin-departamento"

    await ws_manager.broadcast(topic, {
        "type": "NUEVA_TAREA",
        "taskId": payload.get("task_id"),
        "tramiteId": payload.get("tramite_id"),
        "nodeId": payload.get("node_id"),
        "departamentoId": departamento_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.debug("[task_notifier] nueva tarea notificada → topic=%s", topic)
