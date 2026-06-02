from typing import Optional
from datetime import datetime
from beanie import Document


class Departamento(Document):
    nombre: str
    descripcion: Optional[str] = None
    responsableId: Optional[str] = None
    activo: bool = True
    creadoEn: Optional[datetime] = None
    actualizadoEn: Optional[datetime] = None

    class Settings:
        name = "departamentos"
