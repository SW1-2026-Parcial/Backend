"""
Contexto de ejecución del motor de workflow.
Equivale a WorkflowContext.java.
"""
from dataclasses import dataclass, field
from typing import Optional
from models.tramite import Tramite
from models.task import Task
from models.nodo import Nodo


@dataclass
class WorkflowContext:
    tramite: Tramite
    nodo: Nodo
    task: Optional[Task] = None          # task que disparó el avance (puede ser None en arranque)
    branch_selected: Optional[bool] = None  # decisión del funcionario en DECISION
    actor_id: Optional[str] = None       # userId del funcionario que actúa
    form_data: Optional[dict] = None
    comentario: Optional[str] = None
