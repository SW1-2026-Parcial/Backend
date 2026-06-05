"""
Servicio de Azure Blob Storage.
Equivalente a S3 en AWS — almacena los documentos de forma serverless.
"""
import asyncio
import logging
import mimetypes
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from azure.storage.blob import (
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
    BlobSasPermissions,
)
from fastapi import UploadFile

from config import get_settings

logger = logging.getLogger(__name__)

# Extensiones permitidas
EXTENSIONES_PERMITIDAS = {
    "pdf", "docx", "doc", "xlsx", "xls",
    "png", "jpg", "jpeg", "gif", "webp",
    "txt", "csv", "pptx", "ppt",
}


def _get_cliente() -> BlobServiceClient:
    """Crea cliente de Azure Blob Storage desde la connection string."""
    settings = get_settings()
    return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)


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
    tramite_id:  str | None = None,
) -> tuple[str, int, str, str]:
    """
    Sube un archivo a Azure Blob Storage.

    Jerarquía de ruta:
      - Con política y trámite:  {politicaId}/{tramiteId}/{uuid}.{ext}
      - Solo con política:       {politicaId}/{uuid}.{ext}
      - Sin contexto:            general/{uuid}.{ext}

    Retorna: (blob_name, tamano_bytes, mime_type, extension)
    """
    settings = get_settings()
    ext = _extension(file.filename or "archivo")

    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValueError(f"Extensión .{ext} no permitida. Permitidas: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}")

    # Construir ruta jerárquica en el blob
    if politica_id and tramite_id:
        prefix = f"{politica_id}/{tramite_id}"
    elif politica_id:
        prefix = politica_id
    else:
        prefix = "general"

    blob_name = f"{prefix}/{uuid.uuid4()}.{ext}"
    mime = _mime_type(file.filename or "", file.content_type)

    contents = await file.read()
    tamano = len(contents)

    def _subir_sync():
        cliente = _get_cliente()
        blob_client = cliente.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name,
        )
        blob_client.upload_blob(
            contents,
            overwrite=True,
            content_settings=ContentSettings(content_type=mime),
        )

    await asyncio.to_thread(_subir_sync)
    logger.info("Archivo subido a Azure Blob: %s (%d bytes)", blob_name, tamano)
    return blob_name, tamano, mime, ext


def generate_sas_url(blob_name: str, expires_hours: int = 1) -> str:
    """
    Genera una URL con SAS token para descarga temporal (equivalente a S3 presigned URL).
    Expira en `expires_hours` horas.
    """
    settings = get_settings()

    sas_token = generate_blob_sas(
        account_name=settings.azure_storage_account_name,
        container_name=settings.azure_storage_container,
        blob_name=blob_name,
        account_key=settings.azure_storage_account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    )

    url = (
        f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
        f"/{settings.azure_storage_container}/{blob_name}?{sas_token}"
    )
    return url


def generate_sas_url_write(blob_name: str, expires_hours: int = 1) -> str:
    """
    Genera URL con SAS de escritura (para que OnlyOffice pueda guardar el archivo editado).
    """
    settings = get_settings()

    sas_token = generate_blob_sas(
        account_name=settings.azure_storage_account_name,
        container_name=settings.azure_storage_container,
        blob_name=blob_name,
        account_key=settings.azure_storage_account_key,
        permission=BlobSasPermissions(read=True, write=True, create=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    )

    url = (
        f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
        f"/{settings.azure_storage_container}/{blob_name}?{sas_token}"
    )
    return url


async def delete_file(blob_name: str) -> None:
    """Elimina un blob de Azure Storage."""
    settings = get_settings()

    def _eliminar_sync():
        cliente = _get_cliente()
        blob_client = cliente.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name,
        )
        blob_client.delete_blob(delete_snapshots="include")

    await asyncio.to_thread(_eliminar_sync)
    logger.info("Blob eliminado: %s", blob_name)
