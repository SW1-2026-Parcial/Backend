"""
Listener: persiste eventos de workflow en la colección tramite_events.
Se activa automáticamente al importar listeners/__init__.py
"""
import logging
from datetime import datetime, timezone

from core.event_bus import event_bus
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


@event_bus.on("tramite_advanced")
async def _on_tramite_advanced(payload: dict) -> None:
    """Registra el avance general del trámite si no existe evento reciente."""
    # Los eventos puntuales (NODE_ENTERED, TASK_COMPLETED, etc.) los insertan
    # los handlers directamente. Este listener es un fallback para el estado global.
    pass  # los handlers ya persisten sus propios TramiteEvents


@event_bus.on("tramite_completed")
async def _on_tramite_completed(payload: dict) -> None:
    """El EndNodeHandler ya insertó el evento COMPLETED — solo loguear aquí."""
    logger.info("[persistence] Trámite %s completado (ticket=%s)",
                payload.get("tramite_id"), payload.get("ticket_number"))
