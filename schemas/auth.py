from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expiresIn: int
    userId: str
    nombre: str
    rol: str
    email: str          # requerido por el auth.service.ts de Angular
    tipo: str = "Bearer"  # requerido por el auth.service.ts de Angular
