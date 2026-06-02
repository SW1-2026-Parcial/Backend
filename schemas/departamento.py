from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class CreateDepartamentoRequest(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    responsableId: Optional[str] = None


class UpdateDepartamentoRequest(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    responsableId: Optional[str] = None


class DepartamentoResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    responsableId: Optional[str] = None
    activo: bool
    creadoEn: Optional[datetime] = None

    model_config = {"from_attributes": True}
