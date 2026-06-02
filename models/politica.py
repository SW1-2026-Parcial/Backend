from enum import Enum
from typing import Optional
from datetime import datetime
from beanie import Document


class EstadoPolitica(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class Politica(Document):
    nombre: str
    descripcion: Optional[str] = None
    estado: EstadoPolitica = EstadoPolitica.DRAFT
    versionActual: int = 0
    creadoPorId: Optional[str] = None
    creadoEn: Optional[datetime] = None
    actualizadoEn: Optional[datetime] = None

    class Settings:
        name = "politicas"
