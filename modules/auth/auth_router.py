from fastapi import APIRouter
from schemas.auth import LoginRequest, LoginResponse
import modules.auth.auth_service as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    return await auth_service.login(request)
