from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

from models.nodo import TipoNodo


class TipoCampo(str, Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    SELECT = "SELECT"
    FILE = "FILE"
    TEXTAREA = "TEXTAREA"


class CampoDefinicion(BaseModel):
    nombre: str
    etiqueta: str
    tipo: str
    requerido: bool
    opciones: Optional[List[str]] = None


class Destinos(BaseModel):
    nodoDestino: str
    rama: bool
    etiqueta: Optional[str] = None


class PosicionCanvas(BaseModel):
    x: float
    y: float


class Dimensiones(BaseModel):
    ancho: float
    alto: float


class NodoIA(BaseModel):
    nodoId: str
    calleId: Optional[str] = None
    tipoNodo: TipoNodo
    etiqueta: str
    salidas: List[Destinos] = Field(default_factory=list)
    posicionCanvas: PosicionCanvas
    formulario: List[CampoDefinicion] = Field(default_factory=list)
    instruccionAvance: Optional[str] = None
    instruccionRechazo: Optional[str] = None

    @field_validator("salidas", mode="before")
    @classmethod
    def _normalize_salidas(cls, value):
        if value is None:
            return []
        return value

    @field_validator("formulario", mode="before")
    @classmethod
    def _normalize_formulario(cls, value):
        if value is None:
            return []
        return value


class CalleIA(BaseModel):
    calleId: str
    nombre: str
    departamentoId: Optional[str] = None
    posicionCanvas: PosicionCanvas
    dimensiones: Dimensiones
    orden: int


class GenerateRequest(BaseModel):
    instruccion: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Instrucción en lenguaje natural para generar el diagrama UML"
    )
    version_id: str = Field(..., min_length=1)
    calles_actuales: List[CalleIA] = Field(default_factory=list)
    nodos_actuales: List[NodoIA] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    calles: List[CalleIA] = Field(default_factory=list)
    nodos: List[NodoIA] = Field(default_factory=list)
