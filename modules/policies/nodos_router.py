"""
Nodos y conexiones del diagrama UML.
Equivale a NodoController.java + ConexionController.java.
"""
from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin
from core.exceptions import NotFoundException, PoliticaInmutableException
from models.user import User
from models.politica import EstadoPolitica
from models.version_politica import VersionPolitica, Calle
from models.nodo import Nodo, Destinos
from schemas.nodo import (
    CreateNodoRequest, UpdateNodoRequest, ConfigurarNodoRequest,
    CreateConexionRequest, NodoResponse, CalleRequest, UpdateCalleRequest,
)
from schemas.politica import VersionResponse
from core.websocket_manager import ws_manager

router = APIRouter(prefix="/api/versions/{vid}", tags=["nodos"])


async def _get_version_or_404(vid: str) -> VersionPolitica:
    v = await VersionPolitica.get(PydanticObjectId(vid))
    if not v:
        raise NotFoundException("VersionPolitica", vid)
    return v


def _to_response(n: Nodo) -> NodoResponse:
    return NodoResponse(
        id=str(n.id),
        versionPoliticaId=n.versionPoliticaId,
        nodoId=n.nodoId,
        calleId=n.calleId,
        tipoNodo=n.tipoNodo.value,
        etiqueta=n.etiqueta,
        salidas=n.salidas,
        posicionCanvas=n.posicionCanvas,
        formulario=n.formulario,
        instruccionAvance=n.instruccionAvance,
        instruccionRechazo=n.instruccionRechazo,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Nodos
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/nodes", response_model=NodoResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_nodo(vid: str, body: CreateNodoRequest):
    v = await _get_version_or_404(vid)
    from models.politica import EstadoPolitica
    if v.estado != EstadoPolitica.DRAFT:
        raise PoliticaInmutableException()
    nodo = Nodo(
        versionPoliticaId=vid,
        nodoId=body.nodoId or str(uuid.uuid4()),
        calleId=body.calleId,
        tipoNodo=body.tipoNodo,
        etiqueta=body.etiqueta,
        posicionCanvas=body.posicionCanvas,
        creadoEn=datetime.now(timezone.utc),
    )
    await nodo.insert()
    # Broadcast canvas event
    await ws_manager.broadcast(f"canvas/{vid}", {
        "tipo": "NODE_CREATED",
        "nodo": _to_response(nodo).model_dump(),
    })
    return _to_response(nodo)


@router.get("/nodes", response_model=List[NodoResponse])
async def list_nodos(vid: str, _: User = Depends(get_current_user)):
    nodos = await Nodo.find(Nodo.versionPoliticaId == vid).to_list()
    return [_to_response(n) for n in nodos]


@router.get("/nodes/{nodo_id}", response_model=NodoResponse)
async def get_nodo(vid: str, nodo_id: str, _: User = Depends(get_current_user)):
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == nodo_id)
    if not nodo:
        raise NotFoundException("Nodo", nodo_id)
    return _to_response(nodo)


@router.put("/nodes/{nodo_id}", response_model=NodoResponse, dependencies=[Depends(require_admin)])
async def update_nodo(vid: str, nodo_id: str, body: UpdateNodoRequest):
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == nodo_id)
    if not nodo:
        raise NotFoundException("Nodo", nodo_id)
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(nodo, k, v)
    await nodo.save()
    await ws_manager.broadcast(f"canvas/{vid}", {
        "tipo": "NODE_UPDATED",
        "nodo": _to_response(nodo).model_dump(),
    })
    return _to_response(nodo)


@router.patch("/nodes/{nodo_id}/configure", response_model=NodoResponse,
              dependencies=[Depends(require_admin)])
async def configure_nodo(vid: str, nodo_id: str, body: ConfigurarNodoRequest):
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == nodo_id)
    if not nodo:
        raise NotFoundException("Nodo", nodo_id)
    if body.formulario is not None:
        nodo.formulario = body.formulario
    if body.instruccionAvance is not None:
        nodo.instruccionAvance = body.instruccionAvance
    if body.instruccionRechazo is not None:
        nodo.instruccionRechazo = body.instruccionRechazo
    await nodo.save()
    return _to_response(nodo)


@router.delete("/nodes/{nodo_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_nodo(vid: str, nodo_id: str):
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == nodo_id)
    if not nodo:
        raise NotFoundException("Nodo", nodo_id)
    await nodo.delete()
    await ws_manager.broadcast(f"canvas/{vid}", {
        "tipo": "NODE_DELETED",
        "nodoId": nodo_id,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Conexiones
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/connections", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_conexion(vid: str, body: CreateConexionRequest):
    """Agrega una salida (conexión) al nodo origen."""
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == body.origenNodoId)
    if not nodo:
        raise NotFoundException("Nodo origen", body.origenNodoId)
    # Verificar que destino existe
    destino_exists = await Nodo.find_one(
        Nodo.versionPoliticaId == vid, Nodo.nodoId == body.destinoNodoId
    )
    if not destino_exists:
        raise NotFoundException("Nodo destino", body.destinoNodoId)
    # No duplicar
    existing = [s for s in nodo.salidas if s.nodoDestino == body.destinoNodoId]
    if not existing:
        nodo.salidas.append(Destinos(
            nodoDestino=body.destinoNodoId,
            rama=body.rama,
            etiqueta=body.etiqueta,
        ))
        await nodo.save()
    await ws_manager.broadcast(f"canvas/{vid}", {
        "tipo": "CONNECTION_CREATED",
        "origen": body.origenNodoId,
        "destino": body.destinoNodoId,
    })
    return {"message": "Conexión creada"}


@router.delete("/connections/{origen}/{destino}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_conexion(vid: str, origen: str, destino: str):
    nodo = await Nodo.find_one(Nodo.versionPoliticaId == vid, Nodo.nodoId == origen)
    if not nodo:
        raise NotFoundException("Nodo", origen)
    nodo.salidas = [s for s in nodo.salidas if s.nodoDestino != destino]
    await nodo.save()
    await ws_manager.broadcast(f"canvas/{vid}", {
        "tipo": "CONNECTION_DELETED",
        "origen": origen,
        "destino": destino,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Calles (lanes)
# ──────────────────────────────────────────────────────────────────────────────

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


@router.post("/lanes", response_model=VersionResponse,
             dependencies=[Depends(require_admin)])
async def add_calle(vid: str, body: CalleRequest):
    v = await _get_version_or_404(vid)
    if v.estado != EstadoPolitica.DRAFT:
        raise PoliticaInmutableException()
    calle_id = body.calleId or str(uuid.uuid4())
    calle = Calle(
        calleId=calle_id,
        nombre=body.nombre,
        departamentoId=body.departamentoId,
        posicionCanvas=body.posicionCanvas,
        dimensiones=body.dimensiones,
        orden=body.orden,
    )
    v.calles.append(calle)
    await v.save()
    return _version_response(v)


@router.get("/lanes", response_model=List[Calle])
async def list_calles(vid: str, _: User = Depends(get_current_user)):
    v = await _get_version_or_404(vid)
    return v.calles


@router.patch("/lanes/{calle_id}", response_model=VersionResponse,
              dependencies=[Depends(require_admin)])
async def update_calle(vid: str, calle_id: str, body: UpdateCalleRequest):
    v = await _get_version_or_404(vid)
    if v.estado != EstadoPolitica.DRAFT:
        raise PoliticaInmutableException()
    calle = next((c for c in v.calles if c.calleId == calle_id), None)
    if not calle:
        raise NotFoundException("Calle", calle_id)
    updates = body.model_dump(exclude_none=True)
    for k, val in updates.items():
        setattr(calle, k, val)
    await v.save()
    return _version_response(v)


@router.delete("/lanes/{calle_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_calle(vid: str, calle_id: str):
    v = await _get_version_or_404(vid)
    if v.estado != EstadoPolitica.DRAFT:
        raise PoliticaInmutableException()
    v.calles = [c for c in v.calles if c.calleId != calle_id]
    await v.save()
