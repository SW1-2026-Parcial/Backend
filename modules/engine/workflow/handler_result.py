"""
HandlerResult — contrato de retorno de cada NodeHandler.

Hace explícito si el flujo avanza, se detiene o lanza paralelo.
El WorkflowEngine decide qué hacer basándose en este objeto,
sin necesitar conocer el TipoNodo después del hecho.
"""
from dataclasses import dataclass, field


@dataclass
class HandlerResult:
    stop: bool = False
    """True → el flujo se detiene aquí (ACTIVITY esperando tarea, JOIN incompleto)."""

    next_node_ids: list[str] = field(default_factory=list)
    """
    IDs de nodos a procesar a continuación.
    - Vacío → el engine calcula los sucesores desde nodo.salidas.
    - Relleno → el engine usa exactamente estos (útil en FORK para pasar todas las ramas,
      en JOIN solo cuando está sincronizado).
    """

    event_type: str = ""
    """Nombre del evento a emitir en el EventBus (vacío = no emite)."""

    extra: dict = field(default_factory=dict)
    """Payload libre para el EventBus (task_id, tramite_id, etc.)."""
