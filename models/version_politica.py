from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from beanie import Document
from models.politica import EstadoPolitica


class Calle(BaseModel):
    calleId: str
    nombre: str
    departamentoId: Optional[str] = None
    posicionCanvas: Optional[dict] = None
    dimensiones: Optional[dict] = None
    orden: int = 0


class VersionPolitica(Document):
    politicaId: str
    numeroVersion: int
    estado: EstadoPolitica = EstadoPolitica.DRAFT
    calles: List[Calle] = []
    validado: bool = False
    publicadoEn: Optional[datetime] = None
    publicadoPorId: Optional[str] = None
    creadoEn: Optional[datetime] = None

    class Settings:
        name = "versiones_politica"
