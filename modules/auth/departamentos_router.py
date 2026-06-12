from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin
from core.exceptions import NotFoundException
from models.user import User
from models.departamento import Departamento
from schemas.departamento import CreateDepartamentoRequest, UpdateDepartamentoRequest, DepartamentoResponse

router = APIRouter(prefix="/api/departamentos", tags=["departamentos"])


def _to_response(d: Departamento) -> DepartamentoResponse:
    return DepartamentoResponse(
        id=str(d.id),
        nombre=d.nombre,
        descripcion=d.descripcion,
        responsableId=d.responsableId,
        activo=d.activo,
        creadoEn=d.creadoEn,
    )


@router.post("", response_model=DepartamentoResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_departamento(body: CreateDepartamentoRequest):
    dep = Departamento(
        nombre=body.nombre,
        descripcion=body.descripcion,
        responsableId=body.responsableId,
        activo=True,
        creadoEn=datetime.now(timezone.utc),
    )
    await dep.insert()
    return _to_response(dep)


@router.get("", response_model=List[DepartamentoResponse])
async def list_departamentos(_: User = Depends(get_current_user)):
    deps = await Departamento.find(Departamento.activo == True).to_list()
    return [_to_response(d) for d in deps]


@router.get("/{dep_id}", response_model=DepartamentoResponse)
async def get_departamento(dep_id: str, _: User = Depends(get_current_user)):
    dep = await Departamento.get(PydanticObjectId(dep_id))
    if not dep:
        raise NotFoundException("Departamento", dep_id)
    return _to_response(dep)


@router.put("/{dep_id}", response_model=DepartamentoResponse, dependencies=[Depends(require_admin)])
async def update_departamento(dep_id: str, body: UpdateDepartamentoRequest):
    dep = await Departamento.get(PydanticObjectId(dep_id))
    if not dep:
        raise NotFoundException("Departamento", dep_id)
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(dep, k, v)
    dep.actualizadoEn = datetime.now(timezone.utc)
    await dep.save()
    return _to_response(dep)


@router.delete("/{dep_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_departamento(dep_id: str):
    dep = await Departamento.get(PydanticObjectId(dep_id))
    if not dep:
        raise NotFoundException("Departamento", dep_id)
    dep.activo = False
    dep.actualizadoEn = datetime.now(timezone.utc)
    await dep.save()
