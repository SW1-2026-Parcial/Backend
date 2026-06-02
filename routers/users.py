from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from core.security import get_current_user, require_admin
from core.exceptions import NotFoundException, UserAlreadyExistsException
from models.user import User
from schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from core.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _to_response(u: User) -> UserResponse:
    return UserResponse(
        id=str(u.id),
        email=u.email,
        nombre=u.nombre,
        rol=u.rol.value,
        departamentoId=u.departamentoId,
        activo=u.activo,
        creadoEn=u.creadoEn,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_user(body: CreateUserRequest, current: User = Depends(require_admin)):
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise UserAlreadyExistsException(body.email)
    user = User(
        email=body.email,
        passwordHash=hash_password(body.password),
        nombre=body.nombre,
        rol=body.rol,
        departamentoId=body.departamentoId,
        activo=True,
        creadoPor=str(current.id),
        creadoEn=datetime.now(timezone.utc),
    )
    await user.insert()
    return _to_response(user)


@router.get("", response_model=List[UserResponse], dependencies=[Depends(require_admin)])
async def list_users():
    users = await User.find(User.activo == True).to_list()
    return [_to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, _: User = Depends(get_current_user)):
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise NotFoundException("Usuario", user_id)
    return _to_response(user)


@router.put("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def update_user(user_id: str, body: UpdateUserRequest):
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise NotFoundException("Usuario", user_id)
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(user, k, v)
    user.actualizadoEn = datetime.now(timezone.utc)
    await user.save()
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_user(user_id: str):
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise NotFoundException("Usuario", user_id)
    user.activo = False
    user.actualizadoEn = datetime.now(timezone.utc)
    await user.save()
