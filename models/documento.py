from enum import Enum
from typing import Optional, List
from datetime import datetime
from beanie import Document
from pydantic import BaseModel


class NivelPermiso(str, Enum):
    READ = "READ"        # solo lectura / descarga
    WRITE = "WRITE"      # puede editar y subir nueva versión
    DELETE = "DELETE"    # puede eliminar
    ADMIN = "ADMIN"      # todos los permisos incluyendo cambiar permisos


class PermisoDocumento(BaseModel):
    userId: str
    nivel: NivelPermiso


class Documento(Document):
    nombre: str                               # nombre original del archivo
    extension: str                            # pdf, docx, xlsx, png, jpg, etc.
    blobName: str                             # ruta en S3: {polId}/{tramId}/{uuid}.{ext}
    tamano: int                               # tamaño en bytes
    mimeType: str
    # ── Jerarquía: política → trámite ───────────────────────────────────────────
    politicaId: Optional[str] = None          # nivel 1 del árbol
    versionPoliticaId: Optional[str] = None   # versión del proceso (para auditoría)
    tramiteId: Optional[str] = None           # nivel 2 del árbol (ticket)
    clienteId: Optional[str] = None           # quien inició el trámite (denormalizado)
    # ── Auditoría ────────────────────────────────────────────────────────────────
    subidoPorId: str                          # userId de quien subió
    modificadoPorId: Optional[str] = None     # userId de última modificación
    permisos: List[PermisoDocumento] = []     # permisos explícitos por usuario
    activo: bool = True                       # soft delete
    # ── Control de versiones ─────────────────────────────────────────────────────
    version: int = 1                          # número de versión (1, 2, 3...)
    versionAnteriorId: Optional[str] = None   # id del documento versión anterior
    esVersionActual: bool = True              # False en versiones históricas
    creadoEn: datetime
    actualizadoEn: Optional[datetime] = None

    class Settings:
        name = "documentos"
