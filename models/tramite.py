from enum import Enum
from typing import Optional, List
from datetime import datetime
from beanie import Document


class EstadoTramite(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Prioridad(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    URGENT = "URGENT"       # valor heredado del backend Java


class Tramite(Document):
    politicaId: str
    versionPoliticaId: str
    status: EstadoTramite = EstadoTramite.ACTIVE
    currentNodeIds: List[str] = []
    prioridad: Prioridad = Prioridad.MEDIUM
    initiatedBy: Optional[str] = None
    ticketNumber: Optional[str] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    fcmToken: Optional[str] = None

    class Settings:
        name = "tramites"
