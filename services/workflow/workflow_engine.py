"""
WorkflowEngine — orquestador del motor de workflow.
Usa HandlerResult de cada handler para decidir si avanzar, detenerse o paralelizar.
Emite eventos al EventBus para que los listeners reaccionen de forma desacoplada.
"""
import asyncio
import logging
from typing import Optional

from models.nodo import Nodo, TipoNodo
from models.tramite import Tramite, EstadoTramite
from services.workflow.workflow_context import WorkflowContext
from services.workflow.handler_result import HandlerResult
from services.workflow.handlers.base import NodeHandler
from services.workflow.handlers.start_handler import StartNodeHandler
from services.workflow.handlers.activity_handler import ActivityNodeHandler
from services.workflow.handlers.decision_handler import DecisionNodeHandler
from services.workflow.handlers.merge_handler import MergeNodeHandler
from services.workflow.handlers.fork_handler import ForkHandler
from services.workflow.handlers.join_handler import JoinNodeHandler
from services.workflow.handlers.end_handler import EndNodeHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Factory ───────────────────────────────────────────────────────────────────

_HANDLERS: dict[TipoNodo, NodeHandler] = {
    TipoNodo.START:    StartNodeHandler(),
    TipoNodo.ACTIVITY: ActivityNodeHandler(),
    TipoNodo.DECISION: DecisionNodeHandler(),
    TipoNodo.MERGE:    MergeNodeHandler(),
    TipoNodo.FORK:     ForkHandler(),
    TipoNodo.JOIN:     JoinNodeHandler(),
    TipoNodo.END:      EndNodeHandler(),
}


def _get_handler(tipo: TipoNodo) -> NodeHandler:
    handler = _HANDLERS.get(tipo)
    if not handler:
        raise ValueError(f"Sin handler para TipoNodo={tipo}")
    return handler


# ── Motor ─────────────────────────────────────────────────────────────────────

class WorkflowEngine:

    async def start_tramite(self, tramite: Tramite, actor_id: Optional[str] = None) -> None:
        """Busca el nodo START y arranca el flujo."""
        start_node = await Nodo.find_one(
            Nodo.versionPoliticaId == tramite.versionPoliticaId,
            Nodo.tipoNodo == TipoNodo.START,
        )
        if not start_node:
            raise ValueError(f"No hay nodo START en versión {tramite.versionPoliticaId}")

        tramite.currentNodeIds = [start_node.nodoId]
        await tramite.save()

        ctx = WorkflowContext(tramite=tramite, nodo=start_node, actor_id=actor_id)
        await self._run(ctx)

        # Emitir estado tras arrancar
        await self._emit_tramite_advanced(tramite)

    async def advance(
        self,
        tramite: Tramite,
        nodo: Nodo,
        actor_id: Optional[str],
        branch_selected: Optional[bool] = None,
        form_data: Optional[dict] = None,
        comentario: Optional[str] = None,
    ) -> None:
        """Avanza el flujo desde un nodo (llamado después de completar una Task)."""
        ctx = WorkflowContext(
            tramite=tramite,
            nodo=nodo,
            actor_id=actor_id,
            branch_selected=branch_selected,
            form_data=form_data,
            comentario=comentario,
        )
        await self._run(ctx)
        # Recargar y emitir estado actualizado
        tramite_updated = await Tramite.get(tramite.id)
        if tramite_updated:
            await self._emit_tramite_advanced(tramite_updated)

    # ── Ejecución interna ─────────────────────────────────────────────────────

    async def _run(self, ctx: WorkflowContext) -> None:
        """Ejecuta el handler del nodo actual y procesa el HandlerResult."""
        handler = _get_handler(ctx.nodo.tipoNodo)
        result: HandlerResult = await handler.handle(ctx)

        # Emitir evento al bus (listeners reaccionan asíncronamente)
        if result.event_type:
            await event_bus.emit(result.event_type, result.extra)

        if result.stop:
            return

        # Resolver nodos siguientes
        if result.next_node_ids:
            next_ids = result.next_node_ids
        else:
            next_ids = [s.nodoDestino for s in ctx.nodo.salidas]

        if not next_ids:
            logger.warning("[ENGINE] nodo=%s sin sucesores — flujo detenido", ctx.nodo.nodoId)
            return

        # Actualizar currentNodeIds: quitar el nodo actual, añadir los siguientes
        tramite = await Tramite.get(ctx.tramite.id)
        if not tramite or tramite.status != EstadoTramite.ACTIVE:
            return

        current = [n for n in tramite.currentNodeIds if n != ctx.nodo.nodoId]
        for nid in next_ids:
            if nid not in current:
                current.append(nid)
        tramite.currentNodeIds = current
        await tramite.save()

        # Cargar nodos siguientes
        next_nodes = await Nodo.find(
            Nodo.versionPoliticaId == ctx.nodo.versionPoliticaId,
            Nodo.nodoId.in_(next_ids),
        ).to_list()

        if len(next_nodes) == 1:
            next_ctx = WorkflowContext(
                tramite=tramite,
                nodo=next_nodes[0],
                actor_id=ctx.actor_id,
                branch_selected=ctx.branch_selected,
            )
            await self._run(next_ctx)
        elif len(next_nodes) > 1:
            # FORK: procesar todas las ramas en paralelo
            await asyncio.gather(*(
                self._run(WorkflowContext(
                    tramite=tramite,
                    nodo=n,
                    actor_id=ctx.actor_id,
                    branch_selected=ctx.branch_selected,
                ))
                for n in next_nodes
            ))

    async def _emit_tramite_advanced(self, tramite: Tramite) -> None:
        from datetime import datetime, timezone
        await event_bus.emit("tramite_advanced", {
            "tramite_id": str(tramite.id),
            "ticket_number": tramite.ticketNumber,
            "status": tramite.status.value,
            "current_node_ids": tramite.currentNodeIds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Instancia global
workflow_engine = WorkflowEngine()
