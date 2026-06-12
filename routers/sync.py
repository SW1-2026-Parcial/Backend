"""
Sync API para soporte offline del cliente Flutter.
POST /api/sync/pull  → el cliente pide datos actualizados desde una fecha.
POST /api/sync/push  → el cliente envía acciones realizadas offline.
"""
from datetime import datetime, timezone
from typing import List, Optional, Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.security import get_current_user
from models.user import User, Rol
from models.tramite import Tramite, EstadoTramite
from models.task import Task, EstadoTask
from models.nodo import Nodo
from models.politica import Politica, EstadoPolitica
from models.departamento import Departamento
from modules.engine.workflow.workflow_engine import workflow_engine

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PullRequest(BaseModel):
    ultimaSync: Optional[str] = None   # ISO datetime; None = primera sync (todo)


class AccionOffline(BaseModel):
    tipo: str            # COMPLETE_TASK | TAKE_TASK | REJECT_TASK
    entidadId: str       # ID del recurso afectado
    payload: dict = {}   # formData, branchSelected, comentario, etc.
    clientTimestamp: str # ISO datetime de cuando se ejecutó offline


class PushRequest(BaseModel):
    acciones: List[AccionOffline]


class SyncConflicto(BaseModel):
    accionTipo: str
    entidadId: str
    motivo: str


class PushResponse(BaseModel):
    procesadas: int
    errores: int
    conflictos: List[SyncConflicto]


class PullResponse(BaseModel):
    politicas: List[dict]
    tramites: List[dict]
    tareas: List[dict]
    departamentos: List[dict]
    timestamp: str   # momento del servidor para usar como próximo ultimaSync


# ── Pull ─────────────────────────────────────────────────────────────────────

@router.post("/pull", response_model=PullResponse)
async def pull(body: PullRequest, current: User = Depends(get_current_user)):
    """
    Devuelve datos relevantes para el usuario desde ultimaSync.
    - FUNCIONARIO: sus tareas + trámites de su departamento + políticas activas
    - ADMIN/SUPERVISOR: todo
    """
    desde: Optional[datetime] = None
    if body.ultimaSync:
        try:
            desde = datetime.fromisoformat(body.ultimaSync)
            if desde.tzinfo is None:
                desde = desde.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="ultimaSync debe ser ISO 8601")

    # Políticas activas (siempre)
    pols = await Politica.find(Politica.estado == EstadoPolitica.PUBLISHED).to_list()
    politicas_data = [
        {
            "id": str(p.id),
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "estado": p.estado.value,
        }
        for p in pols
    ]

    # Departamentos (siempre)
    deps = await Departamento.find(Departamento.activo == True).to_list()
    deptos_data = [
        {"id": str(d.id), "nombre": d.nombre}
        for d in deps
    ]

    # Tareas
    task_query = [{"status": {"$in": [EstadoTask.PENDING.value, EstadoTask.IN_PROGRESS.value]}}]
    if current.rol == Rol.FUNCIONARIO:
        task_query.append(Task.assignedTo == str(current.id))

    tasks = await Task.find(*task_query).sort("-createdAt").to_list()
    tareas_data = [
        {
            "id": str(t.id),
            "tramiteId": t.tramiteId,
            "nodeId": t.nodeId,
            "departamentoId": t.departamentoId,
            "assignedTo": t.assignedTo,
            "status": t.status.value,
            "formData": t.formData,
            "createdAt": t.createdAt.isoformat() if t.createdAt else None,
        }
        for t in tasks
    ]

    # Trámites
    tramite_ids = list({t.tramiteId for t in tasks})
    tramites_data = []
    if tramite_ids:
        for tid in tramite_ids:
            try:
                tr = await Tramite.get(PydanticObjectId(tid))
                if tr:
                    tramites_data.append({
                        "id": str(tr.id),
                        "ticketNumber": tr.ticketNumber,
                        "status": tr.status.value,
                        "prioridad": tr.prioridad.value,
                        "startedAt": tr.startedAt.isoformat() if tr.startedAt else None,
                        "currentNodeIds": tr.currentNodeIds,
                    })
            except Exception:
                pass

    return PullResponse(
        politicas=politicas_data,
        tramites=tramites_data,
        tareas=tareas_data,
        departamentos=deptos_data,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ── Push ─────────────────────────────────────────────────────────────────────

@router.post("/push", response_model=PushResponse)
async def push(body: PushRequest, current: User = Depends(get_current_user)):
    """
    Procesa acciones realizadas offline por el cliente Flutter.
    Aplica cada acción en orden; si hay conflicto lo registra y continúa.
    """
    procesadas = 0
    errores = 0
    conflictos: list = []

    for accion in body.acciones:
        try:
            if accion.tipo == "TAKE_TASK":
                task = await Task.get(PydanticObjectId(accion.entidadId))
                if not task:
                    raise ValueError("Tarea no encontrada")
                if task.status != EstadoTask.PENDING:
                    conflictos.append({
                        "accionTipo": accion.tipo,
                        "entidadId": accion.entidadId,
                        "motivo": f"Tarea ya en estado {task.status.value}",
                    })
                    continue
                task.assignedTo = str(current.id)
                task.status = EstadoTask.IN_PROGRESS
                task.updatedAt = datetime.now(timezone.utc)
                await task.save()
                procesadas += 1

            elif accion.tipo == "COMPLETE_TASK":
                task = await Task.get(PydanticObjectId(accion.entidadId))
                if not task:
                    raise ValueError("Tarea no encontrada")
                if task.status == EstadoTask.COMPLETED:
                    conflictos.append({
                        "accionTipo": accion.tipo,
                        "entidadId": accion.entidadId,
                        "motivo": "Tarea ya fue completada por otro usuario",
                    })
                    continue
                now = datetime.now(timezone.utc)
                task.status = EstadoTask.COMPLETED
                task.formData = accion.payload.get("formData")
                task.branchSelected = accion.payload.get("branchSelected")
                task.completedAt = now
                task.updatedAt = now
                await task.save()

                # Avanzar motor si el trámite sigue activo
                tr = await Tramite.get(PydanticObjectId(task.tramiteId))
                if tr and tr.status == EstadoTramite.ACTIVE:
                    nodo = await Nodo.find_one(
                        Nodo.versionPoliticaId == tr.versionPoliticaId,
                        Nodo.nodoId == task.nodeId,
                    )
                    if nodo:
                        await workflow_engine.advance(
                            tramite=tr,
                            nodo=nodo,
                            actor_id=str(current.id),
                            branch_selected=accion.payload.get("branchSelected"),
                            form_data=accion.payload.get("formData"),
                        )
                procesadas += 1

            elif accion.tipo == "REJECT_TASK":
                task = await Task.get(PydanticObjectId(accion.entidadId))
                if not task:
                    raise ValueError("Tarea no encontrada")
                if task.status not in (EstadoTask.PENDING, EstadoTask.IN_PROGRESS):
                    conflictos.append({
                        "accionTipo": accion.tipo,
                        "entidadId": accion.entidadId,
                        "motivo": f"No se puede rechazar tarea en estado {task.status.value}",
                    })
                    continue
                task.status = EstadoTask.REJECTED
                task.updatedAt = datetime.now(timezone.utc)
                await task.save()
                procesadas += 1

            else:
                conflictos.append({
                    "accionTipo": accion.tipo,
                    "entidadId": accion.entidadId,
                    "motivo": f"Tipo de acción desconocido: {accion.tipo}",
                })

        except Exception as e:
            errores += 1
            conflictos.append({
                "accionTipo": accion.tipo,
                "entidadId": accion.entidadId,
                "motivo": str(e),
            })

    return PushResponse(procesadas=procesadas, errores=errores, conflictos=conflictos)
