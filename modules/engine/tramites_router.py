"""
Trámites — inicia flujos, consulta estado, historial de eventos.
Equivale a TramiteController.java.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status, HTTPException
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin_or_supervisor
from core.exceptions import NotFoundException, BusinessException
from models.user import User
from models.politica import Politica, EstadoPolitica
from models.version_politica import VersionPolitica
from models.tramite import Tramite, EstadoTramite
from models.tramite_event import TramiteEvent
from models.task import Task
from schemas.tramite import (
    CreateTramiteRequest, TramiteResponse, TramiteEventResponse, FcmTokenRequest
)
from schemas.task import TaskResponse
from modules.engine.ticket_service import generate_ticket
from modules.engine.workflow.workflow_engine import workflow_engine

router = APIRouter(prefix="/api/tramites", tags=["tramites"])


def _to_response(t: Tramite) -> TramiteResponse:
    return TramiteResponse(
        id=str(t.id),
        politicaId=t.politicaId,
        versionPoliticaId=t.versionPoliticaId,
        status=t.status.value,
        currentNodeIds=t.currentNodeIds,
        prioridad=t.prioridad.value,
        initiatedBy=t.initiatedBy,
        ticketNumber=t.ticketNumber,
        startedAt=t.startedAt,
        completedAt=t.completedAt,
    )


@router.get("", response_model=List[TramiteResponse])
async def list_tramites(
    _: User = Depends(require_admin_or_supervisor),
    status_filter: Optional[str] = Query(None, alias="status"),
    politicaId: Optional[str] = Query(None),
):
    query = {}
    if status_filter:
        try:
            query["status"] = EstadoTramite(status_filter)
        except ValueError:
            raise BusinessException(f"Estado inválido: {status_filter}")
    if politicaId:
        query["politicaId"] = politicaId
    tramites = await Tramite.find(query).sort("-startedAt").to_list()
    return [_to_response(t) for t in tramites]


@router.post("", response_model=TramiteResponse, status_code=status.HTTP_201_CREATED)
async def create_tramite(body: CreateTramiteRequest, current: User = Depends(get_current_user)):
    if body.versionPoliticaId:
        version = await VersionPolitica.get(PydanticObjectId(body.versionPoliticaId))
        if not version or version.politicaId != body.politicaId:
            raise NotFoundException("VersionPolitica", body.versionPoliticaId)
        if version.estado != EstadoPolitica.PUBLISHED:
            raise BusinessException("Solo se pueden iniciar trámites sobre versiones publicadas")
    else:
        versions = await VersionPolitica.find(
            VersionPolitica.politicaId == body.politicaId,
            VersionPolitica.estado == EstadoPolitica.PUBLISHED,
        ).sort("-numeroVersion").limit(1).to_list()
        if not versions:
            raise BusinessException("No hay versión publicada para esta política")
        version = versions[0]

    ticket = await generate_ticket()
    tramite = Tramite(
        politicaId=body.politicaId,
        versionPoliticaId=str(version.id),
        status=EstadoTramite.ACTIVE,
        prioridad=body.prioridad,
        initiatedBy=str(current.id),
        ticketNumber=ticket,
        startedAt=datetime.now(timezone.utc),
        fcmToken=body.fcmToken,
    )
    await tramite.insert()

    # Iniciar motor de workflow
    await workflow_engine.start_tramite(tramite, actor_id=str(current.id))

    # Recargar para obtener currentNodeIds actualizados por el motor
    tramite = await Tramite.get(tramite.id)
    return _to_response(tramite)


@router.get("/ticket/{ticket_number}", response_model=TramiteResponse)
async def get_tramite_by_ticket(ticket_number: str):
    """Público — sin auth, para Flutter/móvil."""
    tramite = await Tramite.find_one(Tramite.ticketNumber == ticket_number)
    if not tramite:
        raise NotFoundException("Tramite", ticket_number)
    return _to_response(tramite)


@router.get("/{tramite_id}", response_model=TramiteResponse)
async def get_tramite(tramite_id: str, _: User = Depends(get_current_user)):
    tramite = await Tramite.get(PydanticObjectId(tramite_id))
    if not tramite:
        raise NotFoundException("Tramite", tramite_id)
    return _to_response(tramite)


@router.get("/{tramite_id}/history", response_model=List[TramiteEventResponse])
async def get_history(tramite_id: str, _: User = Depends(get_current_user)):
    events = await TramiteEvent.find(
        TramiteEvent.tramiteId == tramite_id
    ).sort("+timestamp").to_list()
    return [
        TramiteEventResponse(
            id=str(e.id),
            tramiteId=e.tramiteId,
            tipo=e.tipo.value,
            nodeId=e.nodeId,
            taskId=e.taskId,
            actorId=e.actorId,
            formData=e.formData,
            branchTaken=e.branchTaken,
            comentario=e.comentario,
            timestamp=e.timestamp,
        )
        for e in events
    ]


@router.get("/{tramite_id}/tasks", response_model=List[TaskResponse])
async def get_tramite_tasks(tramite_id: str, _: User = Depends(get_current_user)):
    tasks = await Task.find(Task.tramiteId == tramite_id).to_list()
    return [
        TaskResponse(
            id=str(t.id),
            tramiteId=t.tramiteId,
            nodeId=t.nodeId,
            calleId=t.calleId,
            departamentoId=t.departamentoId,
            assignedTo=t.assignedTo,
            status=t.status.value,
            formData=t.formData,
            branchSelected=t.branchSelected,
            createdAt=t.createdAt,
            completedAt=t.completedAt,
        )
        for t in tasks
    ]


@router.post("/ticket/{ticket_number}/fcm-token", status_code=status.HTTP_204_NO_CONTENT)
async def update_fcm_token(ticket_number: str, body: FcmTokenRequest):
    """Actualiza el FCM token del trámite (para notificaciones push móviles)."""
    tramite = await Tramite.find_one(Tramite.ticketNumber == ticket_number)
    if not tramite:
        raise NotFoundException("Tramite", ticket_number)
    tramite.fcmToken = body.fcmToken
    await tramite.save()
