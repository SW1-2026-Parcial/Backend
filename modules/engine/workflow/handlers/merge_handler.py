import logging
from datetime import datetime, timezone

from modules.engine.workflow.handlers.base import NodeHandler
from modules.engine.workflow.workflow_context import WorkflowContext
from modules.engine.workflow.handler_result import HandlerResult
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class MergeNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        logger.debug("[MERGE] nodo=%s tramite=%s", ctx.nodo.nodoId, ctx.tramite.id)
        await TramiteEvent(
            tramiteId=str(ctx.tramite.id),
            tipo=TramiteEventType.MERGE_PASSED,
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            actorId=ctx.actor_id,
            timestamp=datetime.now(timezone.utc),
        ).insert()
        # OR-join: pasa el primero, el engine continúa con las salidas normales
        return HandlerResult(
            event_type="node_processed",
            extra={"tipo_nodo": "MERGE", "tramite_id": str(ctx.tramite.id)},
        )
