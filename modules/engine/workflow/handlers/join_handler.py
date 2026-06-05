import logging
from datetime import datetime, timezone

from modules.engine.workflow.handlers.base import NodeHandler
from modules.engine.workflow.workflow_context import WorkflowContext
from modules.engine.workflow.handler_result import HandlerResult
from models.tramite_event import TramiteEvent, TramiteEventType

logger = logging.getLogger(__name__)

_JOIN_COLLECTION = "tramite_join_tokens"


async def _get_join_col():
    from beanie.odm.utils.init import init_settings
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from beanie import get_db
    return get_db()[_JOIN_COLLECTION]


class JoinNodeHandler(NodeHandler):
    async def handle(self, ctx: WorkflowContext) -> HandlerResult:
        tramite_id = str(ctx.tramite.id)
        nodo_id = ctx.nodo.nodoId
        logger.debug("[JOIN] nodo=%s tramite=%s", nodo_id, tramite_id)

        expected = await _count_incoming_branches(ctx)
        col = await _get_join_col()
        doc_id = f"{tramite_id}:{nodo_id}"

        result = await col.find_one_and_update(
            {"_id": doc_id},
            {"$inc": {"arrivedCount": 1}, "$setOnInsert": {"expectedCount": expected}},
            upsert=True,
            return_document=True,
        )
        arrived = result["arrivedCount"]
        expected_stored = result.get("expectedCount", expected)

        logger.debug("[JOIN] arrived=%d expected=%d", arrived, expected_stored)

        if arrived < expected_stored:
            # Aún faltan ramas — detener este flujo
            return HandlerResult(stop=True)

        # Todas las ramas llegaron — limpiar y avanzar
        await col.delete_one({"_id": doc_id})
        await TramiteEvent(
            tramiteId=tramite_id,
            tipo=TramiteEventType.JOIN_SYNCHRONIZED,
            nodeId=nodo_id,
            calleId=ctx.nodo.calleId,
            actorId=ctx.actor_id,
            timestamp=datetime.now(timezone.utc),
        ).insert()

        logger.info("[JOIN] nodo=%s sincronizado — avanzando", nodo_id)
        return HandlerResult(
            event_type="node_processed",
            extra={"tipo_nodo": "JOIN", "tramite_id": tramite_id},
        )


async def _count_incoming_branches(ctx: WorkflowContext) -> int:
    from models.nodo import Nodo
    count = await Nodo.find(
        Nodo.versionPoliticaId == ctx.nodo.versionPoliticaId,
        {"salidas.nodoDestino": ctx.nodo.nodoId},
    ).count()
    return max(count, 1)
