from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin, require_admin_or_supervisor
from core.exceptions import NotFoundException, BusinessException
from models.user import User
from models.politica import Politica, EstadoPolitica
from schemas.politica import (
    CreatePoliticaRequest, UpdatePoliticaRequest,
    PoliticaResponse, PublicPoliticaResponse,
)

router = APIRouter(prefix="/api/policies", tags=["politicas"])


def _to_response(p: Politica) -> PoliticaResponse:
    return PoliticaResponse(
        id=str(p.id),
        nombre=p.nombre,
        descripcion=p.descripcion,
        estado=p.estado.value,
        versionActual=p.versionActual,
        creadoPorId=p.creadoPorId,
        creadoEn=p.creadoEn,
        actualizadoEn=p.actualizadoEn,
    )


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/public", response_model=List[PublicPoliticaResponse])
async def get_public_policies():
    """Políticas publicadas — sin autenticación (para Flutter)."""
    policies = await Politica.find(Politica.estado == EstadoPolitica.PUBLISHED).to_list()
    return [
        PublicPoliticaResponse(
            id=str(p.id),
            nombre=p.nombre,
            descripcion=p.descripcion,
            versionActual=p.versionActual,
        )
        for p in policies
    ]


# ── Endpoints autenticados ────────────────────────────────────────────────────

@router.post("", response_model=PoliticaResponse, status_code=status.HTTP_201_CREATED)
async def create_politica(body: CreatePoliticaRequest, current: User = Depends(require_admin)):
    pol = Politica(
        nombre=body.nombre,
        descripcion=body.descripcion,
        estado=EstadoPolitica.DRAFT,
        versionActual=0,
        creadoPorId=str(current.id),
        creadoEn=datetime.now(timezone.utc),
    )
    await pol.insert()
    return _to_response(pol)


@router.get("", response_model=List[PoliticaResponse])
async def list_politicas(_: User = Depends(get_current_user)):
    pols = await Politica.find_all().to_list()
    return [_to_response(p) for p in pols]


@router.get("/{pol_id}", response_model=PoliticaResponse)
async def get_politica(pol_id: str, _: User = Depends(get_current_user)):
    pol = await Politica.get(PydanticObjectId(pol_id))
    if not pol:
        raise NotFoundException("Politica", pol_id)
    return _to_response(pol)


@router.put("/{pol_id}", response_model=PoliticaResponse, dependencies=[Depends(require_admin)])
async def update_politica(pol_id: str, body: UpdatePoliticaRequest):
    pol = await Politica.get(PydanticObjectId(pol_id))
    if not pol:
        raise NotFoundException("Politica", pol_id)
    if pol.estado == EstadoPolitica.ARCHIVED:
        raise BusinessException("No se puede modificar una política archivada")
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(pol, k, v)
    pol.actualizadoEn = datetime.now(timezone.utc)
    await pol.save()
    return _to_response(pol)


@router.delete("/{pol_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_politica(pol_id: str):
    pol = await Politica.get(PydanticObjectId(pol_id))
    if not pol:
        raise NotFoundException("Politica", pol_id)
    pol.estado = EstadoPolitica.ARCHIVED
    pol.actualizadoEn = datetime.now(timezone.utc)
    await pol.save()
