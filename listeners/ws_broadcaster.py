"""
Listener: broadcast estado del trámite por WebSocket al topic tramites/{id}.
"""
import logging

from core.event_bus import event_bus
from core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


@event_bus.on("tramite_advanced")
async def _broadcast_tramite_status(payload: dict) -> None:
    tramite_id = payload.get("tramite_id", "")
    topic = f"tramites/{tramite_id}"
    if ws_manager.subscriber_count(topic) == 0:
        return
    await ws_manager.broadcast(topic, {
        "type": "TRAMITE_STATUS",
        "tramiteId": tramite_id,
        "ticketNumber": payload.get("ticket_number"),
        "status": payload.get("status"),
        "currentNodeIds": payload.get("current_node_ids", []),
        "timestamp": payload.get("timestamp"),
    })
    logger.debug("[ws_broadcaster] broadcast → %s", topic)


@event_bus.on("tramite_completed")
async def _broadcast_tramite_completed(payload: dict) -> None:
    tramite_id = payload.get("tramite_id", "")
    topic = f"tramites/{tramite_id}"
    await ws_manager.broadcast(topic, {
        "type": "TRAMITE_COMPLETED",
        "tramiteId": tramite_id,
        "ticketNumber": payload.get("ticket_number"),
        "status": "COMPLETED",
        "timestamp": payload.get("timestamp", ""),
    })
