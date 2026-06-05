"""
Versiones de política: CRUD + publicar + validar + AI-generate.
Equivale a: (CalleController, NodoController dentro del contexto de versión) + lógica de versiones.
"""
from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin, require_admin_or_supervisor
from core.exceptions import NotFoundException, BusinessException, PoliticaInmutableException
from models.user import User, Rol
from models.politica import Politica, EstadoPolitica
from models.version_politica import VersionPolitica
from models.nodo import Nodo, TipoNodo
from schemas.politica import VersionResponse, DiagramaResponse
from schemas.nodo import ValidacionResultado, ValidacionErrorDto, InstruccionRequest
import modules.policies.ai_service as ai_svc
import modules.engine.workflow.workflow_engine as wf_module

router = APIRouter(prefix="/api/policies/{pol_id}/versions", tags=["versiones"])


def _version_response(v: VersionPolitica) -> VersionResponse:
    return VersionResponse(
        id=str(v.id),
        politicaId=v.politicaId,
        numeroVersion=v.numeroVersion,
        estado=v.estado.value,
        calles=v.calles,
        validado=v.validado,
        publicadoEn=v.publicadoEn,
        creadoEn=v.creadoEn,
    )


async def _get_version_or_404(pol_id: str, vid: str) -> VersionPolitica:
    v = await VersionPolitica.get(PydanticObjectId(vid))
    if not v or v.politicaId != pol_id:
        raise NotFoundException("VersionPolitica", vid)
    return v


# ──────────────────────────────────────────────────────────────────────────────
# Versiones CRUD
# ──────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=VersionResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_version(pol_id: str):
    pol = await Politica.get(PydanticObjectId(pol_id))
    if not pol:
        raise NotFoundException("Politica", pol_id)
    if pol.estado == EstadoPolitica.ARCHIVED:
        raise BusinessException("No se pueden crear versiones de políticas archivadas")
    pol.versionActual += 1
    await pol.save()
    v = VersionPolitica(
        politicaId=pol_id,
        numeroVersion=pol.versionActual,
        estado=EstadoPolitica.DRAFT,
        creadoEn=datetime.now(timezone.utc),
    )
    await v.insert()
    return _version_response(v)


@router.get("", response_model=List[VersionResponse])
async def list_versions(pol_id: str, _: User = Depends(get_current_user)):
    versions = await VersionPolitica.find(VersionPolitica.politicaId == pol_id).to_list()
    return [_version_response(v) for v in versions]


@router.get("/{vid}", response_model=VersionResponse)
async def get_version(pol_id: str, vid: str, _: User = Depends(get_current_user)):
    v = await _get_version_or_404(pol_id, vid)
    return _version_response(v)


@router.get("/{vid}/diagram", response_model=DiagramaResponse)
async def get_diagram(pol_id: str, vid: str, _: User = Depends(get_current_user)):
    v = await _get_version_or_404(pol_id, vid)
    nodos = await Nodo.find(Nodo.versionPoliticaId == vid).to_list()
    return DiagramaResponse(
        version=_version_response(v),
        nodos=[n.model_dump(mode="json") for n in nodos],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Publicar y validar
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{vid}/publish", response_model=VersionResponse,
             dependencies=[Depends(require_admin)])
async def publish_version(pol_id: str, vid: str):
    v = await _get_version_or_404(pol_id, vid)
    if v.estado != EstadoPolitica.DRAFT:
        raise BusinessException("Solo se pueden publicar versiones en estado DRAFT")
    if not v.validado:
        raise BusinessException("La versión debe validarse antes de publicar")
    v.estado = EstadoPolitica.PUBLISHED
    v.publicadoEn = datetime.now(timezone.utc)
    await v.save()
    # Actualizar la política también
    pol = await Politica.get(PydanticObjectId(pol_id))
    if pol:
        pol.estado = EstadoPolitica.PUBLISHED
        pol.actualizadoEn = datetime.now(timezone.utc)
        await pol.save()
    return _version_response(v)


@router.post("/{vid}/validate", response_model=ValidacionResultado)
async def validate_version(pol_id: str, vid: str, _: User = Depends(require_admin)):
    v = await _get_version_or_404(pol_id, vid)
    nodos = await Nodo.find(Nodo.versionPoliticaId == vid).to_list()
    errors: list[ValidacionErrorDto] = []

    tipos = {n.tipoNodo for n in nodos}

    # Regla: debe haber exactamente un START
    starts = [n for n in nodos if n.tipoNodo == TipoNodo.START]
    if len(starts) != 1:
        errors.append(ValidacionErrorDto(
            nodoId="*", tipo="MISSING_START",
            mensaje=f"Debe haber exactamente un nodo START (encontrados: {len(starts)})"
        ))

    # Regla: debe haber al menos un END
    ends = [n for n in nodos if n.tipoNodo == TipoNodo.END]
    if not ends:
        errors.append(ValidacionErrorDto(
            nodoId="*", tipo="MISSING_END",
            mensaje="Debe haber al menos un nodo END"
        ))

    # Regla: todos los nodos (excepto END) deben tener al menos una salida
    node_ids = {n.nodoId for n in nodos}
    for n in nodos:
        if n.tipoNodo == TipoNodo.END:
            continue
        if not n.salidas:
            errors.append(ValidacionErrorDto(
                nodoId=n.nodoId, tipo="NO_OUTGOING_CONNECTIONS",
                mensaje=f"El nodo '{n.etiqueta}' no tiene conexiones de salida"
            ))
        # Verificar que los destinos existen
        for s in n.salidas:
            if s.nodoDestino not in node_ids:
                errors.append(ValidacionErrorDto(
                    nodoId=n.nodoId, tipo="INVALID_DESTINATION",
                    mensaje=f"Destino '{s.nodoDestino}' no existe en el diagrama"
                ))

    valido = len(errors) == 0
    if valido:
        v.validado = True
        await v.save()

    return ValidacionResultado(valido=valido, errores=errors)


# ──────────────────────────────────────────────────────────────────────────────
# AI Generate
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{vid}/ai-generate", dependencies=[Depends(require_admin)])
async def ai_generate(pol_id: str, vid: str, body: InstruccionRequest):
    v = await _get_version_or_404(pol_id, vid)
    if v.estado != EstadoPolitica.DRAFT:
        raise PoliticaInmutableException()
    result = await ai_svc.generate_diagram(body.instruccion, vid)
    return result
