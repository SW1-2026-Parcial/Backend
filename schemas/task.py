from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from models.task import EstadoTask


class TaskResponse(BaseModel):
    id: str
    tramiteId: str
    nodeId: str
    calleId: Optional[str] = None
    departamentoId: Optional[str] = None
    assignedTo: Optional[str] = None
    status: str
    formData: Optional[dict] = None
    branchSelected: Optional[bool] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    tramiteTicket: Optional[str] = None
    politicaNombre: Optional[str] = None
    nodoNombre: Optional[str] = None
    departamentoNombre: Optional[str] = None
    prioridad: Optional[str] = None

    model_config = {"from_attributes": True}


class CompletarTareaRequest(BaseModel):
    formData: Optional[dict] = None
    branchSelected: Optional[bool] = None  # para nodos DECISION


class RechazarTareaRequest(BaseModel):
    motivo: Optional[str] = None


class DelegarTareaRequest(BaseModel):
    nuevoAsignadoId: str
