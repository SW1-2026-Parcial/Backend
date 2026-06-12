import logging
from datetime import datetime, timezone

from modules.engine.workflow.handlers.base import NodeHandler
from modules.engine.workflow.workflow_context import WorkflowContext
from modules.engine.workflow.handler_result import HandlerResult
from models.task import Task, EstadoTask
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)


class ActivityNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        logger.debug("[ACTIVITY] nodo=%s tramite=%s", ctx.nodo.nodoId, ctx.tramite.id)

        await TramiteEvent(
            tramiteId=str(ctx.tramite.id),
            tipo=TramiteEventType.NODE_ENTERED,
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            actorId=ctx.actor_id,
            timestamp=datetime.now(timezone.utc),
        ).insert()

        # Resolver departamento desde la calle de la versión
        departamento_id = await _resolve_department(ctx)

        task = Task(
            tramiteId=str(ctx.tramite.id),
            nodeId=ctx.nodo.nodoId,
            calleId=ctx.nodo.calleId,
            departamentoId=departamento_id,
            status=EstadoTask.PENDING,
            createdAt=datetime.now(timezone.utc),
        )
        await task.insert()

        # Añadir nodo a currentNodeIds
        tramite = ctx.tramite
        if ctx.nodo.nodoId not in tramite.currentNodeIds:
            tramite.currentNodeIds.append(ctx.nodo.nodoId)
        await tramite.save()

        logger.info("[ACTIVITY] Task %s creada para nodo=%s", task.id, ctx.nodo.nodoId)
        # stop=True → flujo detenido hasta que el funcionario complete la tarea
        return HandlerResult(
            stop=True,
            event_type="task_created",
            extra={
                "task_id": str(task.id),
                "tramite_id": str(ctx.tramite.id),
                "node_id": ctx.nodo.nodoId,
                "departamento_id": departamento_id,
            },
        )


async def _resolve_department(ctx: WorkflowContext) -> str | None:
    if not ctx.nodo.calleId:
        return None
    try:
        from beanie import PydanticObjectId
        from models.version_politica import VersionPolitica
        version = await VersionPolitica.get(PydanticObjectId(ctx.nodo.versionPoliticaId))
        if version:
            calle = next((c for c in version.calles if c.calleId == ctx.nodo.calleId), None)
            return calle.departamentoId if calle else None
    except Exception:
        pass
    return None
