import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from config import get_settings
from models.user import User, Rol

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


# ──────────────────────────────────────────────────────────────────────────────
# Password helpers  (bcrypt directo — sin passlib, compatible con Spring Security)
# ──────────────────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    """Verifica plain contra un hash BCrypt de Spring Security ($2a$10$...)."""
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt(12)).decode("utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────────────────────────────────────

def create_access_token(email: str, rol: str) -> tuple[str, int]:
    """Retorna (token, expires_in_seconds). Mismo formato que Spring."""
    settings = get_settings()
    expiration_seconds = settings.jwt_expiration_hours * 3600
    expire = datetime.now(timezone.utc) + timedelta(seconds=expiration_seconds)
    payload = {
        "sub": email,
        "rol": rol,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expiration_seconds


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError as e:
        logger.debug("JWT inválido: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────────────────────────────────────
# Dependencies
# ──────────────────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    email: str = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = await User.find_one(User.email == email, User.activo == True)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def require_roles(*roles: Rol):
    """Dependency factory para exigir uno o más roles."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere uno de los roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# Shortcuts
require_admin = require_roles(Rol.ADMINISTRADOR)
require_admin_or_supervisor = require_roles(Rol.ADMINISTRADOR, Rol.SUPERVISOR)
