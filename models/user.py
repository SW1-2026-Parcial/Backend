from enum import Enum
from typing import Optional
from datetime import datetime
from beanie import Document


class Rol(str, Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    SUPERVISOR = "SUPERVISOR"
    FUNCIONARIO = "FUNCIONARIO"


class User(Document):
    email: str
    passwordHash: str
    nombre: str
    rol: Rol
    departamentoId: Optional[str] = None
    activo: bool = True
    fcmToken: Optional[str] = None
    creadoPor: Optional[str] = None
    creadoEn: Optional[datetime] = None
    actualizadoEn: Optional[datetime] = None

    class Settings:
        name = "usuarios"
