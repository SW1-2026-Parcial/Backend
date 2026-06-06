"""
Gestión Documental — Ciclo 2.
Almacena archivos en Azure Blob Storage, metadatos en MongoDB.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin
from core.exceptions import NotFoundException, BusinessException
from models.user import User, Rol
from models.documento import Documento, NivelPermiso, PermisoDocumento
from models.documento_event import DocumentoEvent, TipoEventoDocumento
from schemas.documento import (
    DocumentoResponse,
    DocumentoEventResponse,
    DownloadUrlResponse,
    EditUrlResponse,
    PermisoDocumentoSchema,
    UpdatePermisosRequest,
)
from modules.documents import storage_service as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documentos", tags=["documentos"])

# Mapa extensión → tipo para OnlyOffice
_ONLYOFFICE_TYPE = {
    "docx": "text", "doc": "text", "txt": "text",
    "xlsx": "spreadsheet", "xls": "spreadsheet", "csv": "spreadsheet",
    "pptx": "presentation", "ppt": "presentation",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(doc: Documento) -> DocumentoResponse:
    return DocumentoResponse(
        id=str(doc.id),
        nombre=doc.nombre,
        extension=doc.extension,
        tamano=doc.tamano,
        mimeType=doc.mimeType,
        politicaId=doc.politicaId,
        versionPoliticaId=doc.versionPoliticaId,
        tramiteId=doc.tramiteId,
        clienteId=doc.clienteId,
        subidoPorId=doc.subidoPorId,
        modificadoPorId=doc.modificadoPorId,
        permisos=[PermisoDocumentoSchema(userId=p.userId, nivel=p.nivel) for p in doc.permisos],
        creadoEn=doc.creadoEn,
        actualizadoEn=doc.actualizadoEn,
    )


def _tiene_permiso(doc: Documento, user: User, nivel: NivelPermiso) -> bool:
    """Verifica si el usuario tiene al menos el nivel de permiso requerido."""
    if user.rol == Rol.ADMINISTRADOR:
        return True
    if doc.subidoPorId == str(user.id):
        return True
    orden = [NivelPermiso.READ, NivelPermiso.WRITE, NivelPermiso.DELETE, NivelPermiso.ADMIN]
    idx_requerido = orden.index(nivel)
    for p in doc.permisos:
        if p.userId == str(user.id):
            if orden.index(p.nivel) >= idx_requerido:
                return True
    return False


async def _registrar_evento(
    documento_id: str,
    tipo: TipoEventoDocumento,
    actor_id: str,
    detalles: Optional[dict] = None,
) -> None:
    evento = DocumentoEvent(
        documentoId=documento_id,
        tipo=tipo,
        actorId=actor_id,
        detalles=detalles,
        timestamp=datetime.now(timezone.utc),
    )
    await evento.insert()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def upload_documento(
    file: UploadFile = File(...),
    politicaId: Optional[str] = Form(None),
    versionPoliticaId: Optional[str] = Form(None),
    tramiteId: Optional[str] = Form(None),
    clienteId: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Sube un archivo a Azure Blob Storage y guarda sus metadatos en MongoDB.
    Jerarquía del blob: {politicaId}/{tramiteId}/{uuid}.{ext}
    """
    if not file.filename:
        raise BusinessException("El archivo no tiene nombre")

    try:
        blob_name, tamano, mime_type, extension = await storage.upload_file(
            file,
            politica_id=politicaId,
            tramite_id=tramiteId,
        )
    except ValueError as e:
        raise BusinessException(str(e))

    doc = Documento(
        nombre=file.filename,
        extension=extension,
        blobName=blob_name,
        tamano=tamano,
        mimeType=mime_type,
        politicaId=politicaId,
        versionPoliticaId=versionPoliticaId,
        tramiteId=tramiteId,
        clienteId=clienteId,
        subidoPorId=str(current_user.id),
        permisos=[],
        creadoEn=datetime.now(timezone.utc),
    )
    await doc.insert()

    await _registrar_evento(str(doc.id), TipoEventoDocumento.UPLOADED, str(current_user.id))
    logger.info("Documento subido: %s por %s", file.filename, current_user.email)
    return _to_response(doc)


@router.get("/tree")
async def get_tree(current_user: User = Depends(get_current_user)):
    """
    Devuelve la estructura jerárquica:
      política → trámite (ticketNumber) → documentos
    para poblar el TreeView del repositorio.
    """
    from beanie import PydanticObjectId
    from models.politica import Politica
    from models.tramite import Tramite
    from collections import defaultdict

    docs = await Documento.find({"activo": True}).to_list()

    # Filtrar por permisos si no es admin/supervisor
    if current_user.rol == Rol.FUNCIONARIO:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    # Agrupar: politicaId → tramiteId → [docs]
    arbol: dict = defaultdict(lambda: defaultdict(list))
    sin_tramite: dict = defaultdict(list)  # politicaId → [docs sin tramiteId]

    for d in docs:
        if d.tramiteId:
            arbol[d.politicaId or "sin_politica"][d.tramiteId].append(d)
        else:
            sin_tramite[d.politicaId or "sin_politica"].append(d)

    # Cargar nombres de políticas y trámites (cache en memoria)
    politicas_cache: dict = {}
    tramites_cache: dict  = {}

    async def _nombre_politica(pid: str) -> str:
        if pid not in politicas_cache:
            try:
                p = await Politica.get(PydanticObjectId(pid))
                politicas_cache[pid] = p.nombre if p else pid
            except Exception:
                politicas_cache[pid] = pid
        return politicas_cache[pid]

    async def _ticket_tramite(tid: str) -> str:
        if tid not in tramites_cache:
            try:
                t = await Tramite.get(PydanticObjectId(tid))
                tramites_cache[tid] = t.ticketNumber or tid if t else tid
            except Exception:
                tramites_cache[tid] = tid
        return tramites_cache[tid]

    result = []
    all_pol_ids = set(list(arbol.keys()) + list(sin_tramite.keys()))

    for pol_id in all_pol_ids:
        pol_nombre = await _nombre_politica(pol_id) if pol_id != "sin_politica" else "Sin política"
        children = []

        for tram_id, tram_docs in arbol[pol_id].items():
            ticket = await _ticket_tramite(tram_id)
            children.append({
                "key":      f"{pol_id}_{tram_id}",
                "label":    ticket,
                "type":     "tramite",
                "tramiteId": tram_id,
                "children": [
                    {
                        "key":   str(d.id),
                        "label": d.nombre,
                        "type":  "documento",
                        "data":  _to_response(d).model_dump(),
                    }
                    for d in sorted(tram_docs, key=lambda x: x.creadoEn, reverse=True)
                ],
            })

        # Documentos sin trámite asociado (nivel directo bajo política)
        for d in sin_tramite[pol_id]:
            children.append({
                "key":   str(d.id),
                "label": d.nombre,
                "type":  "documento",
                "data":  _to_response(d).model_dump(),
            })

        result.append({
            "key":       pol_id,
            "label":     pol_nombre,
            "type":      "politica",
            "politicaId": pol_id,
            "children":  children,
        })

    return result


@router.get("/public/tramite/{tramite_id}", response_model=List[DocumentoResponse])
async def public_docs_by_tramite(tramite_id: str):
    """Endpoint público — el mobile consulta documentos de un trámite sin JWT."""
    docs = await Documento.find(
        {"tramiteId": tramite_id, "activo": True}
    ).sort("-creadoEn").to_list()
    return [_to_response(d) for d in docs]


@router.get("", response_model=List[DocumentoResponse])
async def list_documentos(
    politicaId: Optional[str] = Query(None),
    tramiteId: Optional[str] = Query(None),
    clienteId: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Lista documentos con filtros opcionales."""
    query: dict = {"activo": True}
    if politicaId:
        query["politicaId"] = politicaId
    if tramiteId:
        query["tramiteId"] = tramiteId
    if clienteId:
        query["clienteId"] = clienteId

    docs = await Documento.find(query).sort("-creadoEn").to_list()

    # Filtrar por permisos (si no es admin, solo muestra los que puede ver)
    if current_user.rol != Rol.ADMINISTRADOR:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    return [_to_response(d) for d in docs]


@router.get("/por-politica/{politica_id}", response_model=List[DocumentoResponse])
async def docs_por_politica(
    politica_id: str,
    current_user: User = Depends(get_current_user),
):
    """Repositorio de documentos organizados por política."""
    docs = await Documento.find(
        {"politicaId": politica_id, "activo": True}
    ).sort("-creadoEn").to_list()

    if current_user.rol != Rol.ADMINISTRADOR:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    return [_to_response(d) for d in docs]


@router.get("/por-cliente/{cliente_id}", response_model=List[DocumentoResponse])
async def docs_por_cliente(
    cliente_id: str,
    current_user: User = Depends(get_current_user),
):
    """Repositorio personal del cliente."""
    docs = await Documento.find(
        {"clienteId": cliente_id, "activo": True}
    ).sort("-creadoEn").to_list()

    if current_user.rol != Rol.ADMINISTRADOR:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    return [_to_response(d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentoResponse)
async def get_documento(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Obtiene los metadatos de un documento."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.READ):
        raise HTTPException(status_code=403, detail="Sin permiso para ver este documento")

    await _registrar_evento(str(doc.id), TipoEventoDocumento.VIEWED, str(current_user.id))
    return _to_response(doc)


@router.get("/{doc_id}/download", response_model=DownloadUrlResponse)
async def get_download_url(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Genera una URL SAS temporal para descargar el archivo (expira en 1 hora)."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.READ):
        raise HTTPException(status_code=403, detail="Sin permiso para descargar este documento")

    url = storage.generate_sas_url(doc.blobName, expires_hours=1)
    await _registrar_evento(str(doc.id), TipoEventoDocumento.DOWNLOADED, str(current_user.id))
    return DownloadUrlResponse(url=url, expiraEn=3600)


@router.post("/{doc_id}/edit-url", response_model=EditUrlResponse)
async def get_edit_url(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Genera la config necesaria para abrir el documento en OnlyOffice.
    El frontend usa este objeto para inicializar el editor.
    Incluye un JWT firmado que OnlyOffice verifica.
    """
    import jwt as pyjwt
    from config import get_settings
    settings = get_settings()

    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.WRITE):
        raise HTTPException(status_code=403, detail="Sin permiso para editar este documento")

    doc_type = _ONLYOFFICE_TYPE.get(doc.extension, "text")
    read_url = storage.generate_sas_url(doc.blobName, expires_hours=2)
    callback_url = f"{settings.backend_url}/api/documentos/{doc_id}/onlyoffice-callback"
    doc_key = f"{doc_id}-{int(doc.actualizadoEn.timestamp() if doc.actualizadoEn else doc.creadoEn.timestamp())}"

    # Config de OnlyOffice
    oo_config = {
        "document": {
            "fileType": doc.extension,
            "key": doc_key,
            "title": doc.nombre,
            "url": read_url,
        },
        "documentType": doc_type,
        "editorConfig": {
            "callbackUrl": callback_url,
            "lang": "es",
            "user": {
                "id": str(current_user.id),
                "name": current_user.nombre or current_user.email,
            },
            "mode": "edit",
            "customization": {
                "autosave": True,
                "forcesave": True,
            },
        },
    }

    # Firmar con JWT para que OnlyOffice lo acepte
    token = pyjwt.encode(oo_config, settings.onlyoffice_secret, algorithm="HS256")

    return EditUrlResponse(
        documentUrl=read_url,
        callbackUrl=callback_url,
        documentKey=doc_key,
        documentType=doc_type,
        nombre=doc.nombre,
        token=token,
        onlyofficeUrl=settings.onlyoffice_public_url,
        config=oo_config,
    )


@router.post("/{doc_id}/onlyoffice-callback", status_code=status.HTTP_200_OK)
async def onlyoffice_callback(doc_id: str, body: dict):
    """
    Endpoint que OnlyOffice llama cuando el usuario guarda el documento.
    status 2 = documento listo para guardar, downloadUrl tiene el archivo nuevo.
    """
    if body.get("status") != 2:
        return {"error": 0}

    download_url = body.get("url")
    if not download_url:
        return {"error": 0}

    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        return {"error": 1}

    # Descargar el archivo editado y subir de vuelta al mismo blob
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get(download_url)
        r.raise_for_status()
        contenido = r.content

    import asyncio
    from azure.storage.blob import ContentSettings

    def _actualizar_blob():
        from modules.documents.storage_service import _get_cliente
        from config import get_settings
        settings = get_settings()
        blob_client = _get_cliente().get_blob_client(
            container=settings.azure_storage_container,
            blob=doc.blobName,
        )
        blob_client.upload_blob(
            contenido,
            overwrite=True,
            content_settings=ContentSettings(content_type=doc.mimeType),
        )

    await asyncio.to_thread(_actualizar_blob)

    doc.tamano = len(contenido)
    doc.actualizadoEn = datetime.now(timezone.utc)
    await doc.save()

    await _registrar_evento(str(doc.id), TipoEventoDocumento.EDITED, "onlyoffice")
    logger.info("Documento actualizado por OnlyOffice: %s", doc.nombre)
    return {"error": 0}


@router.put("/{doc_id}/permisos", response_model=DocumentoResponse)
async def update_permisos(
    doc_id: str,
    body: UpdatePermisosRequest,
    current_user: User = Depends(get_current_user),
):
    """Reemplaza los permisos del documento. Solo el dueño o admin."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.ADMIN):
        raise HTTPException(status_code=403, detail="Solo el dueño o admin puede cambiar permisos")

    permisos_anteriores = [{"userId": p.userId, "nivel": p.nivel} for p in doc.permisos]

    doc.permisos = [
        PermisoDocumento(userId=p.userId, nivel=p.nivel)
        for p in body.permisos
    ]
    doc.actualizadoEn = datetime.now(timezone.utc)
    await doc.save()

    await _registrar_evento(
        str(doc.id),
        TipoEventoDocumento.PERMISSION_CHANGED,
        str(current_user.id),
        detalles={"anteriores": permisos_anteriores, "nuevos": [p.dict() for p in body.permisos]},
    )
    return _to_response(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_documento(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Soft delete: marca el documento como inactivo y elimina el blob de Azure."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.DELETE):
        raise HTTPException(status_code=403, detail="Sin permiso para eliminar este documento")

    # Eliminar el blob de Azure
    try:
        await storage.delete_file(doc.blobName)
    except Exception as e:
        logger.warning("No se pudo eliminar blob %s: %s", doc.blobName, e)

    doc.activo = False
    doc.actualizadoEn = datetime.now(timezone.utc)
    await doc.save()

    await _registrar_evento(str(doc.id), TipoEventoDocumento.DELETED, str(current_user.id))


@router.get("/{doc_id}/historial", response_model=List[DocumentoEventResponse])
async def get_historial(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Historial de eventos del documento (quién lo subió, editó, descargó, etc.)."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.READ):
        raise HTTPException(status_code=403, detail="Sin permiso para ver este documento")

    eventos = await DocumentoEvent.find(
        DocumentoEvent.documentoId == doc_id
    ).sort("+timestamp").to_list()

    return [
        DocumentoEventResponse(
            id=str(e.id),
            documentoId=e.documentoId,
            tipo=e.tipo.value,
            actorId=e.actorId,
            detalles=e.detalles,
            timestamp=e.timestamp,
        )
        for e in eventos
    ]
