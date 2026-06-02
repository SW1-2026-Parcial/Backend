"""
WebSocket pub/sub manager.
Reemplaza STOMP — topics idénticos: canvas/{id}, tramites/{id}, tareas/{userId}, alertas.
El frontend Angular usa STOMP.js; para migrar: ver nota en routers/ws.py.
"""
import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Gestiona conexiones activas agrupadas por topic."""

    def __init__(self):
        # topic → set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, topic: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[topic].add(ws)
        logger.debug("WS conectado → topic=%s  total=%d", topic, len(self._connections[topic]))

    async def disconnect(self, topic: str, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[topic].discard(ws)
            if not self._connections[topic]:
                del self._connections[topic]
        logger.debug("WS desconectado → topic=%s", topic)

    async def broadcast(self, topic: str, payload: Any) -> None:
        """Emite el payload (dict o str) a todos los clientes suscritos al topic."""
        message = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        dead: list[WebSocket] = []
        async with self._lock:
            sockets = set(self._connections.get(topic, set()))
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(topic, ws)

    def subscriber_count(self, topic: str) -> int:
        return len(self._connections.get(topic, set()))


# Instancia global compartida por todos los routers
ws_manager = WebSocketManager()
