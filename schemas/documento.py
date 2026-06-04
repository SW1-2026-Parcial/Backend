from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from models.documento import NivelPermiso
from models.documento_event import TipoEventoDocumento


# ── Permisos ──────────────────────────────────────────────────────────────────

class PermisoDocumentoSchema(BaseModel):
    userId: str
    nivel: NivelPermiso

    model_config = {"from_attributes": True}


# ── Documento ─────────────────────────────────────────────────────────────────

class DocumentoResponse(BaseModel):
    id: str
    nombre: str
    extension: str
    tamano: int
    mimeType: str
    politicaId: Optional[str] = None
    versionPoliticaId: Optional[str] = None
    tramiteId: Optional[str] = None
    clienteId: Optional[str] = None
    subidoPorId: str
    modificadoPorId: Optional[str] = None
    permisos: List[PermisoDocumentoSchema] = []
    creadoEn: datetime
    actualizadoEn: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UpdatePermisosRequest(BaseModel):
    """Reemplaza toda la lista de permisos del documento."""
    permisos: List[PermisoDocumentoSchema]


# ── Descarga / Edición ────────────────────────────────────────────────────────

class DownloadUrlResponse(BaseModel):
    url: str
    expiraEn: int  # segundos


class EditUrlResponse(BaseModel):
    """Config para inicializar el editor OnlyOffice en el frontend."""
    documentUrl: str        # URL SAS de lectura del blob
    callbackUrl: str        # URL del backend para que OnlyOffice guarde
    documentKey: str        # ID único del documento (para cache de OnlyOffice)
    documentType: str       # text | spreadsheet | presentation
    nombre: str
    token: Optional[str] = None           # JWT firmado para OnlyOffice
    onlyofficeUrl: Optional[str] = None   # URL del Document Server
    config: Optional[dict] = None         # Config completa para el JS SDK


# ── Eventos ───────────────────────────────────────────────────────────────────

class DocumentoEventResponse(BaseModel):
    id: str
    documentoId: str
    tipo: str
    actorId: str
    detalles: Optional[dict] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
