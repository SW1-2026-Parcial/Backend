"""
Servicio de Amazon S3.
Almacena documentos corporativos en la nube con URLs presignadas para acceso temporal.
"""
import asyncio
import logging
import mimetypes
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from config import get_settings

logger = logging.getLogger(__name__)

EXTENSIONES_PERMITIDAS = {
    "pdf", "docx", "doc", "xlsx", "xls",
    "png", "jpg", "jpeg", "gif", "webp",
    "txt", "csv", "pptx", "ppt",
}


def _get_cliente():
    """Crea cliente de Amazon S3 desde las credenciales configuradas."""
    settings = get_settings()
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def _extension(filename: str) -> str:
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "bin"


def _mime_type(filename: str, content_type: Optional[str]) -> str:
    if content_type and content_type != "application/octet-stream":
        return content_type
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


async def upload_file(
    file: UploadFile,
    politica_id: str | None = None,
    tramite_id: str | None = None,
) -> tuple[str, int, str, str]:
    """
    Sube un archivo a Amazon S3.

    Jerarquía de ruta:
      - Con política y trámite:  {politicaId}/{tramiteId}/{uuid}.{ext}
      - Solo con política:       {politicaId}/{uuid}.{ext}
      - Sin contexto:            general/{uuid}.{ext}

    Retorna: (s3_key, tamano_bytes, mime_type, extension)
    """
    settings = get_settings()
    ext = _extension(file.filename or "archivo")

    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValueError(
            f"Extensión .{ext} no permitida. Permitidas: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}"
        )

    if politica_id and tramite_id:
        prefix = f"{politica_id}/{tramite_id}"
    elif politica_id:
        prefix = politica_id
    else:
        prefix = "general"

    s3_key = f"{prefix}/{uuid.uuid4()}.{ext}"
    mime = _mime_type(file.filename or "", file.content_type)
    contents = await file.read()
    tamano = len(contents)

    def _subir_sync():
        cliente = _get_cliente()
        cliente.put_object(
            Bucket=settings.aws_bucket,
            Key=s3_key,
            Body=contents,
            ContentType=mime,
        )

    await asyncio.to_thread(_subir_sync)
    logger.info("Archivo subido a S3: %s (%d bytes)", s3_key, tamano)
    return s3_key, tamano, mime, ext


def generate_sas_url(s3_key: str, expires_hours: int = 1) -> str:
    """
    Genera URL presignada de lectura temporal (equivalente a SAS de Azure).
    Expira en `expires_hours` horas.
    """
    settings = get_settings()
    cliente = _get_cliente()

    url = cliente.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.aws_bucket, "Key": s3_key},
        ExpiresIn=expires_hours * 3600,
    )
    return url


def generate_sas_url_write(s3_key: str, expires_hours: int = 1) -> str:
    """
    Genera URL presignada de escritura (para que OnlyOffice pueda guardar el archivo editado).
    """
    settings = get_settings()
    cliente = _get_cliente()

    url = cliente.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.aws_bucket,
            "Key": s3_key,
            "ContentType": "application/octet-stream",
        },
        ExpiresIn=expires_hours * 3600,
    )
    return url


async def delete_file(s3_key: str) -> None:
    """Elimina un objeto de Amazon S3."""
    settings = get_settings()

    def _eliminar_sync():
        cliente = _get_cliente()
        cliente.delete_object(Bucket=settings.aws_bucket, Key=s3_key)

    await asyncio.to_thread(_eliminar_sync)
    logger.info("Objeto S3 eliminado: %s", s3_key)
