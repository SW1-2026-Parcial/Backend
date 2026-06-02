from fastapi import HTTPException, status
from models.user import User
from core.security import verify_password, create_access_token
from schemas.auth import LoginRequest, LoginResponse


async def login(request: LoginRequest) -> LoginResponse:
    user = await User.find_one(User.email == request.email.strip().lower())
    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    if not verify_password(request.password, user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    token, expires_in = create_access_token(user.email, user.rol.value)
    return LoginResponse(
        token=token,
        expiresIn=expires_in,
        userId=str(user.id),
        nombre=user.nombre,
        rol=user.rol.value,
        email=user.email,
    )
