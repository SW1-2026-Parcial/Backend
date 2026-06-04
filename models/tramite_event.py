from enum import Enum
from typing import Optional
from datetime import datetime
from beanie import Document


class TramiteEventType(str, Enum):
    STARTED = "STARTED"
    NODE_ENTERED = "NODE_ENTERED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_REJECTED = "TASK_REJECTED"
    DECISION_TAKEN = "DECISION_TAKEN"
    FORK_SPLIT = "FORK_SPLIT"
    JOIN_SYNCHRONIZED = "JOIN_SYNCHRONIZED"
    MERGE_PASSED = "MERGE_PASSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TramiteEvent(Document):
    tramiteId: str
    tipo: TramiteEventType
    nodeId: Optional[str] = None
    calleId: Optional[str] = None
    departamentoId: Optional[str] = None
    taskId: Optional[str] = None      # ID de la Task asociada (para TASK_COMPLETED/REJECTED)
    actorId: Optional[str] = None
    formData: Optional[dict] = None
    branchTaken: Optional[bool] = None
    comentario: Optional[str] = None
    timestamp: datetime

    class Settings:
        name = "tramite_events"
