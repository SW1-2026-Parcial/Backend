from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from models.politica import EstadoPolitica
from models.version_politica import Calle


class CreatePoliticaRequest(BaseModel):
    nombre: str
    descripcion: Optional[str] = None


class UpdatePoliticaRequest(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None


class PoliticaResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    estado: str
    versionActual: int
    creadoPorId: Optional[str] = None
    creadoEn: Optional[datetime] = None
    actualizadoEn: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PublicPoliticaResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    versionActual: int


# ── Versiones ─────────────────────────────────────────────────────────────────

class CreateVersionRequest(BaseModel):
    """Crea una nueva versión en estado DRAFT para una política."""
    pass  # la numeración la asigna el backend


class VersionResponse(BaseModel):
    id: str
    politicaId: str
    numeroVersion: int
    estado: str
    calles: List[Calle] = []
    validado: bool
    publicadoEn: Optional[datetime] = None
    creadoEn: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DiagramaResponse(BaseModel):
    """Version + nodos juntos — para el canvas."""
    version: VersionResponse
    calles: List[Calle] = []
    nodos: List[dict] = []
