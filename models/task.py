from enum import Enum
from typing import Optional
from datetime import datetime
from beanie import Document


class EstadoTask(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class Task(Document):
    tramiteId: str
    nodeId: str
    calleId: Optional[str] = None
    departamentoId: Optional[str] = None
    assignedTo: Optional[str] = None
    status: EstadoTask = EstadoTask.PENDING
    formData: Optional[dict] = None
    branchSelected: Optional[bool] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None

    class Settings:
        name = "tasks"
