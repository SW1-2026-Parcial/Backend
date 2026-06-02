from enum import Enum
from typing import Optional
from datetime import datetime
from beanie import Document


class TipoEventoDocumento(str, Enum):
    UPLOADED = "UPLOADED"
    VIEWED = "VIEWED"
    EDITED = "EDITED"
    DELETED = "DELETED"
    DOWNLOADED = "DOWNLOADED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"


class DocumentoEvent(Document):
    documentoId: str
    tipo: TipoEventoDocumento
    actorId: str
    detalles: Optional[dict] = None         # info extra (ej: permisos anteriores/nuevos)
    timestamp: datetime

    class Settings:
        name = "documento_events"
