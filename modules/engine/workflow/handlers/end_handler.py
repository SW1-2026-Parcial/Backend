import logging
from datetime import datetime, timezone

from modules.engine.workflow.handlers.base import NodeHandler
from modules.engine.workflow.workflow_context import WorkflowContext
from modules.engine.workflow.handler_result import HandlerResult
from models.tramite import EstadoTramite
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class EndNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        logger.info("[END] nodo=%s tramite=%s → COMPLETADO", ctx.nodo.nodoId, ctx.tramite.id)
        tramite = ctx.tramite
        tramite.status = EstadoTramite.COMPLETED
        tramite.completedAt = datetime.now(timezone.utc)
        tramite.currentNodeIds = []
        await tramite.save()

        await TramiteEvent(
            tramiteId=str(tramite.id),
            tipo=TramiteEventType.COMPLETED,
            nodeId=ctx.nodo.nodoId,
            actorId=ctx.actor_id,
            timestamp=datetime.now(timezone.utc),
        ).insert()

        # stop=True: no hay sucesores que procesar
        return HandlerResult(
            stop=True,
            event_type="tramite_completed",
            extra={
                "tramite_id": str(tramite.id),
                "ticket_number": tramite.ticketNumber,
            },
        )
