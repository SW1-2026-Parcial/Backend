"""
CanvasSessionManager — gestiona presencia en el canvas colaborativo.
Equivale a CanvasSessionManager.java.

Mantiene en memoria quién está editando cada versión de política.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class PresenciaInfo:
    userId: str
    nombre: str
    color: str       # color asignado al cursor (HEX)
    desde: str       # ISO timestamp de cuándo entró
    ultimaActividad: str


# Paleta de colores para cursores
_COLORES = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
]


class CanvasSessionManager:
    def __init__(self):
        # versionId → { userId → PresenciaInfo }
        self._sessions: dict[str, dict[str, PresenciaInfo]] = {}
        self._lock = asyncio.Lock()

    async def join(self, version_id: str, user_id: str, nombre: str) -> PresenciaInfo:
        async with self._lock:
            if version_id not in self._sessions:
                self._sessions[version_id] = {}
            session = self._sessions[version_id]
            # Asignar color no usado
            used = {p.color for p in session.values()}
            color = next((c for c in _COLORES if c not in used), _COLORES[0])
            now = datetime.now(timezone.utc).isoformat()
            info = PresenciaInfo(
                userId=user_id,
                nombre=nombre,
                color=color,
                desde=now,
                ultimaActividad=now,
            )
            session[user_id] = info
            return info

    async def leave(self, version_id: str, user_id: str) -> None:
        async with self._lock:
            if version_id in self._sessions:
                self._sessions[version_id].pop(user_id, None)
                if not self._sessions[version_id]:
                    del self._sessions[version_id]

    async def get_presence(self, version_id: str) -> list[dict]:
        async with self._lock:
            session = self._sessions.get(version_id, {})
            return [
                {
                    "userId": p.userId,
                    "nombre": p.nombre,
                    "color": p.color,
                    "desde": p.desde,
                }
                for p in session.values()
            ]

    async def ping(self, version_id: str, user_id: str) -> None:
        async with self._lock:
            session = self._sessions.get(version_id)
            if session and user_id in session:
                session[user_id].ultimaActividad = datetime.now(timezone.utc).isoformat()


# Instancia global
canvas_session_manager = CanvasSessionManager()
