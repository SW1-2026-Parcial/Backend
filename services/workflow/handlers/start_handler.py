import logging
from datetime import datetime, timezone

from services.workflow.handlers.base import NodeHandler
from services.workflow.workflow_context import WorkflowContext
from services.workflow.handler_result import HandlerResult
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class StartNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        logger.debug("[START] nodo=%s tramite=%s", ctx.nodo.nodoId, ctx.tramite.id)
        await TramiteEvent(
            tramiteId=str(ctx.tramite.id),
            tipo=TramiteEventType.NODE_ENTERED,
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            timestamp=datetime.now(timezone.utc),
        ).insert()
        # Avanza normalmente — el engine lee nodo.salidas
        return HandlerResult(
            event_type="node_processed",
            extra={"tipo_nodo": "START", "node_id": ctx.nodo.nodoId,
                   "tramite_id": str(ctx.tramite.id)},
        )
