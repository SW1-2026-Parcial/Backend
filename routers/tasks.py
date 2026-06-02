"""
Tareas del funcionario: bandeja, tomar, completar, rechazar, delegar.
Equivale a TaskController.java + TaskServiceImpl.java.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException
from beanie import PydanticObjectId

from core.security import get_current_user
from core.exceptions import NotFoundException, BusinessException
from models.user import User, Rol
from models.task import Task, EstadoTask
from models.tramite import Tramite, EstadoTramite
from models.tramite_event import TramiteEvent, TramiteEventType
from models.nodo import Nodo
from schemas.task import TaskResponse, CompletarTareaRequest, RechazarTareaRequest, DelegarTareaRequest
from services.workflow.workflow_engine import workflow_engine

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _to_response(t: Task) -> TaskResponse:
    return TaskResponse(
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


# ── Consultas ─────────────────────────────────────────────────────────────────

@router.get("/my-tasks", response_model=List[TaskResponse])
async def my_tasks(current: User = Depends(get_current_user)):
    """Tareas asignadas al funcionario logueado."""
    tasks = await Task.find(
        Task.assignedTo == str(current.id),
        Task.status.in_([EstadoTask.PENDING, EstadoTask.IN_PROGRESS]),
    ).sort("-createdAt").to_list()
    return [_to_response(t) for t in tasks]


@router.get("/available", response_model=List[TaskResponse])
async def available_tasks(current: User = Depends(get_current_user)):
    """Tareas sin asignar del departamento del funcionario logueado."""
    query_conditions = [
        Task.status == EstadoTask.PENDING,
        Task.assignedTo == None,
    ]
    if current.departamentoId:
        query_conditions.append(Task.departamentoId == current.departamentoId)

    tasks = await Task.find(*query_conditions).sort("-createdAt").to_list()
    return [_to_response(t) for t in tasks]


# ── Acciones ──────────────────────────────────────────────────────────────────

@router.patch("/{task_id}/take", response_model=TaskResponse)
async def take_task(task_id: str, current: User = Depends(get_current_user)):
    """El funcionario toma una tarea sin asignar."""
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        raise NotFoundException("Task", task_id)
    if task.status != EstadoTask.PENDING:
        raise BusinessException("Solo se pueden tomar tareas en estado PENDING")
    if task.assignedTo and task.assignedTo != str(current.id):
        raise BusinessException("La tarea ya está asignada a otro funcionario")

    task.assignedTo = str(current.id)
    task.status = EstadoTask.IN_PROGRESS
    task.updatedAt = datetime.now(timezone.utc)
    await task.save()
    return _to_response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    body: CompletarTareaRequest,
    current: User = Depends(get_current_user),
):
    """Completa una tarea y avanza el motor de workflow."""
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        raise NotFoundException("Task", task_id)
    if task.status not in (EstadoTask.PENDING, EstadoTask.IN_PROGRESS):
        raise BusinessException(f"No se puede completar una tarea en estado {task.status}")

    now = datetime.now(timezone.utc)
    task.status = EstadoTask.COMPLETED
    task.formData = body.formData
    task.branchSelected = body.branchSelected
    task.assignedTo = task.assignedTo or str(current.id)
    task.completedAt = now
    task.updatedAt = now
    await task.save()

    # Registrar evento de auditoría
    await TramiteEvent(
        tramiteId=task.tramiteId,
        tipo=TramiteEventType.TASK_COMPLETED,
        nodeId=task.nodeId,
        calleId=task.calleId,
        actorId=str(current.id),
        formData=body.formData,
        timestamp=now,
    ).insert()

    # Avanzar motor de workflow
    tramite = await Tramite.get(PydanticObjectId(task.tramiteId))
    if not tramite:
        raise NotFoundException("Tramite", task.tramiteId)
    if tramite.status == EstadoTramite.ACTIVE:
        nodo = await Nodo.find_one(
            Nodo.versionPoliticaId == tramite.versionPoliticaId,
            Nodo.nodoId == task.nodeId,
        )
        if nodo:
            await workflow_engine.advance(
                tramite=tramite,
                nodo=nodo,
                actor_id=str(current.id),
                branch_selected=body.branchSelected,
                form_data=body.formData,
            )

    return _to_response(task)


@router.post("/{task_id}/reject", response_model=TaskResponse)
async def reject_task(
    task_id: str,
    body: RechazarTareaRequest,
    current: User = Depends(get_current_user),
):
    """Rechaza una tarea. El trámite queda en estado REJECTED."""
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        raise NotFoundException("Task", task_id)
    if task.status not in (EstadoTask.PENDING, EstadoTask.IN_PROGRESS):
        raise BusinessException(f"No se puede rechazar una tarea en estado {task.status}")

    now = datetime.now(timezone.utc)
    task.status = EstadoTask.REJECTED
    task.updatedAt = now
    await task.save()

    await TramiteEvent(
        tramiteId=task.tramiteId,
        tipo=TramiteEventType.TASK_REJECTED,
        nodeId=task.nodeId,
        actorId=str(current.id),
        comentario=body.comentario,
        timestamp=now,
    ).insert()

    # Marcar el trámite como REJECTED
    tramite = await Tramite.get(PydanticObjectId(task.tramiteId))
    if tramite and tramite.status == EstadoTramite.ACTIVE:
        tramite.status = EstadoTramite.REJECTED
        tramite.completedAt = now
        await tramite.save()

    return _to_response(task)


@router.post("/{task_id}/delegate", response_model=TaskResponse)
async def delegate_task(
    task_id: str,
    body: DelegarTareaRequest,
    current: User = Depends(get_current_user),
):
    """Reasigna una tarea a otro funcionario."""
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        raise NotFoundException("Task", task_id)
    if task.status == EstadoTask.COMPLETED:
        raise BusinessException("No se puede delegar una tarea ya completada")

    # Verificar que el nuevo asignado existe
    nuevo = await User.get(PydanticObjectId(body.nuevoAsignadoId))
    if not nuevo or not nuevo.activo:
        raise NotFoundException("Usuario", body.nuevoAsignadoId)
    if nuevo.rol != Rol.FUNCIONARIO:
        raise BusinessException("Solo se puede delegar a funcionarios")

    task.assignedTo = body.nuevoAsignadoId
    task.status = EstadoTask.PENDING
    task.updatedAt = datetime.now(timezone.utc)
    await task.save()
    return _to_response(task)
