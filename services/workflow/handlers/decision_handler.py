import logging
from datetime import datetime, timezone

from services.workflow.handlers.base import NodeHandler
from services.workflow.workflow_context import WorkflowContext
from services.workflow.handler_result import HandlerResult
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class DecisionNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        branch = ctx.branch_selected if ctx.branch_selected is not None else False
        if ctx.branch_selected is None:
            logger.warning("[DECISION] branchSelected es None en nodo=%s tramite=%s — asume False",
                           ctx.nodo.nodoId, ctx.tramite.id)

        await TramiteEvent(
            tramiteId=str(ctx.tramite.id),
            tipo=TramiteEventType.DECISION_TAKEN,
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            actorId=ctx.actor_id,
            branchTaken=branch,
            timestamp=datetime.now(timezone.utc),
        ).insert()

        # Filtrar la única salida cuya rama coincide con branch
        salidas = [s for s in ctx.nodo.salidas if s.rama == branch]
        if not salidas:
            salidas = ctx.nodo.salidas[:1]  # fallback: primera disponible

        next_ids = [s.nodoDestino for s in salidas]
        return HandlerResult(
            next_node_ids=next_ids,
            event_type="node_processed",
            extra={"tipo_nodo": "DECISION", "branch": branch,
                   "tramite_id": str(ctx.tramite.id)},
        )
