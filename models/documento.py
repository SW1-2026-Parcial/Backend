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
    nombre: str                             # nombre original del archivo
    extension: str                          # pdf, docx, xlsx, png, jpg, etc.
    blobName: str                           # ruta en Azure Blob (ej: documentos/uuid.pdf)
    tamano: int                             # tamaño en bytes
    mimeType: str
    politicaId: Optional[str] = None        # política a la que pertenece
    tramiteId: Optional[str] = None         # trámite al que está adjunto
    clienteId: Optional[str] = None         # repositorio del cliente
    subidoPorId: str                        # userId de quien subió
    modificadoPorId: Optional[str] = None  # userId de última modificación
    permisos: List[PermisoDocumento] = []  # permisos explícitos por usuario
    activo: bool = True                     # soft delete
    creadoEn: datetime
    actualizadoEn: Optional[datetime] = None

    class Settings:
        name = "documentos"
