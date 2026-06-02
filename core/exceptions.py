from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    def __init__(self, resource: str, id_: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} con id '{id_}' no encontrado",
        )


class BusinessException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
        super().__init__(status_code=status_code, detail=detail)


class UserAlreadyExistsException(HTTPException):
    def __init__(self, email: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con email '{email}'",
        )


class PoliticaInmutableException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo se pueden modificar versiones en estado DRAFT",
        )


class AiServiceException(HTTPException):
    def __init__(self, detail: str = "Error comunicando con el servicio de IA"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
