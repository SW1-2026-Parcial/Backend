from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from models.nodo import TipoNodo, Destinos, CampoDefinicion


class CreateNodoRequest(BaseModel):
    nodoId: Optional[str] = None   # se autogenera si no se envía (compatible con frontend)
    calleId: Optional[str] = None
    tipoNodo: TipoNodo
    etiqueta: str
    posicionCanvas: Optional[dict] = None


class UpdateNodoRequest(BaseModel):
    calleId: Optional[str] = None
    etiqueta: Optional[str] = None
    posicionCanvas: Optional[dict] = None


class ConfigurarNodoRequest(BaseModel):
    formulario: Optional[List[CampoDefinicion]] = None
    instruccionAvance: Optional[str] = None
    instruccionRechazo: Optional[str] = None


class CreateConexionRequest(BaseModel):
    origenNodoId: str
    destinoNodoId: str
    etiqueta: Optional[str] = None
    rama: bool = True


class NodoResponse(BaseModel):
    id: str
    versionPoliticaId: str
    nodoId: str
    calleId: Optional[str] = None
    tipoNodo: str
    etiqueta: str
    salidas: List[Destinos] = []
    posicionCanvas: Optional[dict] = None
    formulario: List[CampoDefinicion] = []
    instruccionAvance: Optional[str] = None
    instruccionRechazo: Optional[str] = None

    model_config = {"from_attributes": True}


class CalleRequest(BaseModel):
    calleId: Optional[str] = None  # si no se pasa, el backend genera UUID
    nombre: str
    departamentoId: Optional[str] = None
    posicionCanvas: Optional[dict] = None
    dimensiones: Optional[dict] = None
    orden: int = 0


class UpdateCalleRequest(BaseModel):
    nombre: Optional[str] = None
    departamentoId: Optional[str] = None
    posicionCanvas: Optional[dict] = None
    dimensiones: Optional[dict] = None
    orden: Optional[int] = None


class ValidacionErrorDto(BaseModel):
    nodoId: str
    tipo: str
    mensaje: str


class ValidacionResultado(BaseModel):
    valido: bool
    errores: List[ValidacionErrorDto] = []


class InstruccionRequest(BaseModel):
    instruccion: str
    version_id: str
