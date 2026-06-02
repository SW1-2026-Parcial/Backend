from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator
from models.user import Rol


class CreateUserRequest(BaseModel):
    email: str
    password: str
    nombre: str
    rol: Rol
    departamentoId: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()


class UpdateUserRequest(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[Rol] = None
    departamentoId: Optional[str] = None
    activo: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    email: str
    nombre: str
    rol: str
    departamentoId: Optional[str] = None
    activo: bool
    creadoEn: Optional[datetime] = None

    model_config = {"from_attributes": True}
