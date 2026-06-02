import logging
from datetime import datetime, timezone

from services.workflow.handlers.base import NodeHandler
from services.workflow.workflow_context import WorkflowContext
from services.workflow.handler_result import HandlerResult
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class ForkHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        logger.debug("[FORK] nodo=%s tramite=%s salidas=%d",
                     ctx.nodo.nodoId, ctx.tramite.id, len(ctx.nodo.salidas))
        await TramiteEvent(
            tramiteId=str(ctx.tramite.id),
            tipo=TramiteEventType.FORK_SPLIT,
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            actorId=ctx.actor_id,
            timestamp=datetime.now(timezone.utc),
        ).insert()
        # Retorna TODAS las salidas — el engine las procesa en paralelo con asyncio.gather
        all_destinations = [s.nodoDestino for s in ctx.nodo.salidas]
        return HandlerResult(
            next_node_ids=all_destinations,
            event_type="node_processed",
            extra={"tipo_nodo": "FORK", "tramite_id": str(ctx.tramite.id),
                   "ramas": len(all_destinations)},
        )
