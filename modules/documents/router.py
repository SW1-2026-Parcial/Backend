"""
Gestión Documental — Ciclo 2.
Almacena archivos en Amazon S3, metadatos en MongoDB.
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
        version=doc.version,
        versionAnteriorId=doc.versionAnteriorId,
        esVersionActual=doc.esVersionActual,
        creadoEn=doc.creadoEn,
        actualizadoEn=doc.actualizadoEn,
    )


def _tiene_permiso(doc: Documento, user: User, nivel: NivelPermiso) -> bool:
    """Verifica si el usuario tiene al menos el nivel de permiso requerido.
    Acceso implícito: administradores y supervisores del departamento del trámite."""
    if user.rol == Rol.ADMINISTRADOR:
        return True
    if user.rol == Rol.SUPERVISOR:
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


async def _asignar_permisos_automaticos(tramite_id: str) -> list[PermisoDocumento]:
    """Asigna permisos automáticos: funcionario que tomó la tarea + supervisores del depto."""
    from models.task import Task
    permisos: list[PermisoDocumento] = []
    seen_users: set[str] = set()

    # Buscar tasks del trámite para obtener assignedTo y departamentoId
    tasks = await Task.find({"tramiteId": tramite_id}).to_list()

    for task in tasks:
        # Funcionario asignado → WRITE
        if task.assignedTo and task.assignedTo not in seen_users:
            permisos.append(PermisoDocumento(userId=task.assignedTo, nivel=NivelPermiso.WRITE))
            seen_users.add(task.assignedTo)

        # Supervisores del departamento de la tarea → WRITE
        if task.departamentoId:
            supervisores = await User.find(
                User.rol == Rol.SUPERVISOR,
                User.departamentoId == task.departamentoId,
                User.activo == True,
            ).to_list()
            for sup in supervisores:
                uid = str(sup.id)
                if uid not in seen_users:
                    permisos.append(PermisoDocumento(userId=uid, nivel=NivelPermiso.WRITE))
                    seen_users.add(uid)

    return permisos


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

    # Si hay tramiteId pero no politicaId, resolver desde el trámite
    if tramiteId and not politicaId:
        from models.tramite import Tramite
        try:
            tramite = await Tramite.get(PydanticObjectId(tramiteId))
            if tramite:
                politicaId = tramite.politicaId
                versionPoliticaId = versionPoliticaId or tramite.versionPoliticaId
        except Exception:
            pass

    try:
        blob_name, tamano, mime_type, extension = await storage.upload_file(
            file,
            politica_id=politicaId,
            tramite_id=tramiteId,
        )
    except ValueError as e:
        raise BusinessException(str(e))

    # Auto-asignar permisos si hay trámite asociado
    permisos_auto = []
    if tramiteId:
        permisos_auto = await _asignar_permisos_automaticos(tramiteId)

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
        permisos=permisos_auto,
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


# ── Lazy tree endpoints ───────────────────────────────────────────────────────

@router.get("/tree/politicas")
async def tree_politicas(current_user: User = Depends(get_current_user)):
    """Devuelve solo el nivel de políticas con conteo de documentos (sin cargar hijos)."""
    from models.politica import Politica
    from collections import Counter

    docs = await Documento.find({"activo": True}).to_list()

    if current_user.rol == Rol.FUNCIONARIO:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    counts: Counter = Counter(d.politicaId or "sin_politica" for d in docs)
    pol_ids = [pid for pid in counts if pid != "sin_politica"]

    politicas_objs = await Politica.find(
        {"_id": {"$in": [PydanticObjectId(pid) for pid in pol_ids]}}
    ).to_list() if pol_ids else []
    nombre_map = {str(p.id): p.nombre for p in politicas_objs}

    result = []
    for pol_id, total in sorted(counts.items(), key=lambda x: nombre_map.get(x[0], x[0])):
        label = nombre_map.get(pol_id, "Sin política") if pol_id != "sin_politica" else "Sin política"
        result.append({
            "key": pol_id,
            "label": label,
            "type": "politica",
            "politicaId": pol_id,
            "leaf": False,
            "data": {"count": total},
        })
    return result


@router.get("/tree/tramites/{politica_id}")
async def tree_tramites(
    politica_id: str,
    current_user: User = Depends(get_current_user),
):
    """Devuelve trámites de una política con conteo de documentos."""
    from models.tramite import Tramite
    from collections import Counter

    query = {"politicaId": politica_id, "activo": True} if politica_id != "sin_politica" else {"politicaId": None, "activo": True}
    docs = await Documento.find(query).to_list()

    if current_user.rol == Rol.FUNCIONARIO:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    counts: Counter = Counter(d.tramiteId or "sin_tramite" for d in docs)
    tram_ids = [tid for tid in counts if tid != "sin_tramite"]

    tramites_objs = await Tramite.find(
        {"_id": {"$in": [PydanticObjectId(tid) for tid in tram_ids]}}
    ).to_list() if tram_ids else []
    ticket_map = {str(t.id): t.ticketNumber or str(t.id) for t in tramites_objs}

    result = []
    for tram_id, total in sorted(counts.items(), key=lambda x: ticket_map.get(x[0], x[0]), reverse=True):
        label = ticket_map.get(tram_id, tram_id) if tram_id != "sin_tramite" else "Sin trámite"
        result.append({
            "key": f"{politica_id}_{tram_id}",
            "label": label,
            "type": "tramite",
            "tramiteId": tram_id,
            "leaf": False,
            "data": {"count": total},
        })
    return result


@router.get("/tree/documentos/{tramite_id}")
async def tree_documentos(
    tramite_id: str,
    current_user: User = Depends(get_current_user),
):
    """Devuelve documentos de un trámite, ordenados por fecha desc."""
    query = {"tramiteId": tramite_id, "activo": True} if tramite_id != "sin_tramite" else {"tramiteId": None, "activo": True}
    docs = await Documento.find(query).sort("-creadoEn").to_list()

    if current_user.rol == Rol.FUNCIONARIO:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    return [
        {
            "key": str(d.id),
            "label": d.nombre,
            "type": "documento",
            "leaf": True,
            "data": _to_response(d).model_dump(),
        }
        for d in docs
    ]


@router.get("/public/tramite/{tramite_id}", response_model=List[DocumentoResponse])
async def public_docs_by_tramite(tramite_id: str):
    """Endpoint público — el mobile consulta documentos de un trámite sin JWT."""
    docs = await Documento.find(
        {"tramiteId": tramite_id, "activo": True}
    ).sort("-creadoEn").to_list()
    return [_to_response(d) for d in docs]


@router.post("/public/upload", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def public_upload_documento(
    file: UploadFile = File(...),
    tramiteId: str = Form(...),
    clienteId: Optional[str] = Form(None),
):
    """
    Sube un documento desde la app móvil sin JWT.
    Solo permite asociar documentos a trámites existentes (tramiteId obligatorio).
    """
    if not file.filename:
        raise BusinessException("El archivo no tiene nombre")

    # Verificar que el trámite existe
    from models.tramite import Tramite
    from beanie import PydanticObjectId
    try:
        tramite = await Tramite.get(PydanticObjectId(tramiteId))
    except Exception:
        tramite = None
    if tramite is None:
        raise NotFoundException("Tramite", tramiteId)

    try:
        blob_name, tamano, mime_type, extension = await storage.upload_file(
            file,
            politica_id=tramite.politicaId,
            tramite_id=tramiteId,
        )
    except ValueError as e:
        raise BusinessException(str(e))

    # Auto-asignar permisos
    permisos_auto = await _asignar_permisos_automaticos(tramiteId)

    doc = Documento(
        nombre=file.filename,
        extension=extension,
        blobName=blob_name,
        tamano=tamano,
        mimeType=mime_type,
        politicaId=tramite.politicaId,
        versionPoliticaId=tramite.versionPoliticaId,
        tramiteId=tramiteId,
        clienteId=clienteId,
        subidoPorId="mobile_agent",
        permisos=permisos_auto,
        creadoEn=datetime.now(timezone.utc),
    )
    await doc.insert()

    await _registrar_evento(str(doc.id), TipoEventoDocumento.UPLOADED, "mobile_agent")
    logger.info("Documento subido (móvil): %s para trámite %s", file.filename, tramiteId)
    return _to_response(doc)


@router.get("", response_model=List[DocumentoResponse])
async def list_documentos(
    politicaId: Optional[str] = Query(None),
    tramiteId: Optional[str] = Query(None),
    clienteId: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(15, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Lista documentos con filtros opcionales y paginación."""
    query: dict = {"activo": True}
    if politicaId:
        query["politicaId"] = politicaId
    if tramiteId:
        query["tramiteId"] = tramiteId
    if clienteId:
        query["clienteId"] = clienteId

    total = await Documento.find(query).count()
    skip = (page - 1) * per_page
    docs = await Documento.find(query).sort("-creadoEn").skip(skip).limit(per_page).to_list()

    if current_user.rol != Rol.ADMINISTRADOR:
        docs = [d for d in docs if _tiene_permiso(d, current_user, NivelPermiso.READ)]

    from fastapi.responses import JSONResponse
    return JSONResponse(content={
        "data": [_to_response(d).model_dump(mode="json") for d in docs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


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


@router.get("/{doc_id}/detalle")
async def get_documento_detalle(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Detalle enriquecido: metadatos + nombres de usuarios + historial simplificado."""
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.READ):
        raise HTTPException(status_code=403, detail="Sin permiso para ver este documento")

    # Resolver nombres de usuarios
    user_ids = {doc.subidoPorId}
    if doc.modificadoPorId:
        user_ids.add(doc.modificadoPorId)
    for p in doc.permisos:
        user_ids.add(p.userId)

    # Cargar eventos simplificados (solo UPLOADED y EDITED)
    eventos = await DocumentoEvent.find(
        DocumentoEvent.documentoId == doc_id,
        {"tipo": {"$in": [TipoEventoDocumento.UPLOADED.value, TipoEventoDocumento.EDITED.value]}},
    ).sort("+timestamp").to_list()

    for ev in eventos:
        user_ids.add(ev.actorId)

    # Resolver todos los nombres de una vez
    nombre_map: dict[str, str] = {}
    for uid in user_ids:
        if uid == "mobile_agent":
            nombre_map[uid] = "App Móvil"
            continue
        if uid == "onlyoffice":
            nombre_map[uid] = "Editor OnlyOffice"
            continue
        try:
            u = await User.get(PydanticObjectId(uid))
            nombre_map[uid] = u.nombre if u else uid
        except Exception:
            nombre_map[uid] = uid

    # Historial simplificado
    historial = []
    for ev in eventos:
        historial.append({
            "tipo": ev.tipo.value,
            "actorId": ev.actorId,
            "actorNombre": nombre_map.get(ev.actorId, ev.actorId),
            "timestamp": ev.timestamp.isoformat(),
        })

    # Permisos con nombres
    permisos_con_nombre = []
    for p in doc.permisos:
        permisos_con_nombre.append({
            "userId": p.userId,
            "nombre": nombre_map.get(p.userId, p.userId),
            "nivel": p.nivel.value,
        })

    await _registrar_evento(str(doc.id), TipoEventoDocumento.VIEWED, str(current_user.id))

    return {
        **_to_response(doc).model_dump(),
        "subidoPorNombre": nombre_map.get(doc.subidoPorId, doc.subidoPorId),
        "modificadoPorNombre": nombre_map.get(doc.modificadoPorId, "") if doc.modificadoPorId else None,
        "permisosDetalle": permisos_con_nombre,
        "historial": historial,
    }


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

    def _actualizar_s3():
        from modules.documents.storage_service import _get_cliente
        from config import get_settings
        settings = get_settings()
        _get_cliente().put_object(
            Bucket=settings.aws_bucket,
            Key=doc.blobName,
            Body=contenido,
            ContentType=doc.mimeType,
        )

    await asyncio.to_thread(_actualizar_s3)

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


# ── Control de versiones ──────────────────────────────────────────────────────

@router.post("/{doc_id}/nueva-version", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def nueva_version(
    doc_id: str,
    archivo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Sube una nueva versión de un documento existente.
    - Marca la versión anterior como esVersionActual=False
    - Crea nuevo documento con version+1 y versionAnteriorId apuntando al anterior
    - Hereda permisos, tramiteId y politicaId del documento original
    """
    doc_anterior = await Documento.get(PydanticObjectId(doc_id))
    if not doc_anterior or not doc_anterior.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc_anterior, current_user, NivelPermiso.WRITE):
        raise HTTPException(status_code=403, detail="Sin permiso para versionar este documento")

    # Subir nuevo archivo a S3
    blob_name, tamano, mime_type, extension = await storage.upload_file(
        archivo,
        politica_id=doc_anterior.politicaId,
        tramite_id=doc_anterior.tramiteId,
    )

    ahora = datetime.now(timezone.utc)

    # Marcar versión anterior como histórica
    doc_anterior.esVersionActual = False
    doc_anterior.actualizadoEn = ahora
    await doc_anterior.save()

    # Crear nueva versión
    nuevo_doc = Documento(
        nombre=doc_anterior.nombre,
        extension=extension,
        blobName=blob_name,
        tamano=tamano,
        mimeType=mime_type,
        politicaId=doc_anterior.politicaId,
        versionPoliticaId=doc_anterior.versionPoliticaId,
        tramiteId=doc_anterior.tramiteId,
        clienteId=doc_anterior.clienteId,
        subidoPorId=str(current_user.id),
        modificadoPorId=str(current_user.id),
        permisos=doc_anterior.permisos,
        activo=True,
        version=doc_anterior.version + 1,
        versionAnteriorId=str(doc_anterior.id),
        esVersionActual=True,
        creadoEn=ahora,
        actualizadoEn=ahora,
    )
    await nuevo_doc.insert()

    # Registrar evento
    await DocumentoEvent(
        documentoId=str(nuevo_doc.id),
        tipo=TipoEventoDocumento.UPLOADED,
        actorId=str(current_user.id),
        detalles={"version": nuevo_doc.version, "versionAnteriorId": str(doc_anterior.id)},
        timestamp=ahora,
    ).insert()

    return _to_response(nuevo_doc)


@router.get("/{doc_id}/versiones", response_model=List[DocumentoResponse])
async def get_versiones(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Devuelve el historial completo de versiones de un documento,
    desde la versión actual hacia atrás.
    """
    doc = await Documento.get(PydanticObjectId(doc_id))
    if not doc or not doc.activo:
        raise NotFoundException("Documento", doc_id)
    if not _tiene_permiso(doc, current_user, NivelPermiso.READ):
        raise HTTPException(status_code=403, detail="Sin permiso")

    versiones = [doc]
    actual = doc
    while actual.versionAnteriorId:
        anterior = await Documento.get(PydanticObjectId(actual.versionAnteriorId))
        if not anterior:
            break
        versiones.append(anterior)
        actual = anterior

    return [_to_response(v) for v in versiones]
