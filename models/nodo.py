from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from beanie import Document


class TipoNodo(str, Enum):
    START = "START"
    END = "END"
    ACTIVITY = "ACTIVITY"
    DECISION = "DECISION"
    MERGE = "MERGE"
    FORK = "FORK"
    JOIN = "JOIN"


class Destinos(BaseModel):
    nodoDestino: str
    rama: bool = True
    etiqueta: Optional[str] = None


class CampoDefinicion(BaseModel):
    nombre: str
    etiqueta: str
    tipo: str  # TEXT, NUMBER, DATE, SELECT, FILE, TEXTAREA
    requerido: bool = False
    opciones: Optional[List[str]] = None


class Nodo(Document):
    versionPoliticaId: str
    nodoId: str
    calleId: Optional[str] = None
    tipoNodo: TipoNodo
    etiqueta: str
    salidas: List[Destinos] = []
    posicionCanvas: Optional[dict] = None
    formulario: List[CampoDefinicion] = []
    instruccionAvance: Optional[str] = None
    instruccionRechazo: Optional[str] = None
    creadoEn: Optional[datetime] = None

    class Settings:
        name = "nodos"
