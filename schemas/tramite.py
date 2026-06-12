from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from models.tramite import EstadoTramite, Prioridad
from models.tramite_event import TramiteEventType


class CreateTramiteRequest(BaseModel):
    politicaId: str
    versionPoliticaId: Optional[str] = None
    prioridad: Prioridad = Prioridad.MEDIUM
    fcmToken: Optional[str] = None


class TramiteResponse(BaseModel):
    id: str
    politicaId: str
    versionPoliticaId: str
    status: str
    currentNodeIds: List[str] = []
    prioridad: str
    initiatedBy: Optional[str] = None
    ticketNumber: Optional[str] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TramiteEventResponse(BaseModel):
    id: str
    tramiteId: str
    tipo: str
    nodeId: Optional[str] = None
    taskId: Optional[str] = None
    actorId: Optional[str] = None
    formData: Optional[dict] = None
    branchTaken: Optional[bool] = None
    comentario: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class FcmTokenRequest(BaseModel):
    fcmToken: str


# ── WebSocket payloads ────────────────────────────────────────────────────────

class TramiteEstadoWsPayload(BaseModel):
    tramiteId: str
    ticketNumber: Optional[str] = None
    status: str
    currentNodeIds: List[str] = []
    timestamp: str


class TareaNotificacionWsPayload(BaseModel):
    taskId: str
    tramiteId: str
    nodeId: str
    tipo: str = "NUEVA_TAREA"
