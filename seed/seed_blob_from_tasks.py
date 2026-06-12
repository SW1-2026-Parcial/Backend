"""
Sube archivos placeholder a Azure Blob Storage para todas las URLs
referenciadas en formData de tasks.json.

Esto hace que los links de documentos en los formularios de tareas
apunten a archivos reales en Azure.

Uso:
    cd sp1-backend-py
    python seed/seed_blob_from_tasks.py              # sube todo
    python seed/seed_blob_from_tasks.py --dry-run    # solo muestra qué haría
"""
import io
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "documentos")

MIME_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def generar_pdf(nombre: str) -> bytes:
    """PDF mínimo válido con contenido."""
    text = f"Documento: {nombre} — Generado por seed SP1-BPM"
    # Sanitizar para latin-1 (PDF básico)
    safe_text = text.encode("latin-1", errors="replace").decode("latin-1")
    stream = f"BT /F1 12 Tf 50 700 Td ({safe_text}) Tj ET".encode("latin-1")
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n"
        + stream + b"\nendstream\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000340 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )


def generar_jpg_placeholder() -> bytes:
    """JPEG mínimo válido (1x1 pixel)."""
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x7B,
        0x94, 0x11, 0x00, 0x00, 0xFF, 0xD9,
    ])


def generar_png_placeholder() -> bytes:
    """PNG mínimo válido (1x1 pixel blanco)."""
    import struct, zlib
    # IHDR
    width, height = 1, 1
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    # IDAT
    raw_data = zlib.compress(b"\x00\xFF\xFF\xFF")
    idat_crc = zlib.crc32(b"IDAT" + raw_data) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw_data)) + b"IDAT" + raw_data + struct.pack(">I", idat_crc)
    # IEND
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def generar_contenido(blob_name: str) -> tuple[bytes, str]:
    """Genera contenido y mime type según extensión del blob."""
    ext = blob_name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return generar_pdf(blob_name), MIME_TYPES["pdf"]
    elif ext in ("jpg", "jpeg"):
        return generar_jpg_placeholder(), MIME_TYPES["jpg"]
    elif ext == "png":
        return generar_png_placeholder(), MIME_TYPES["png"]
    else:
        return f"Placeholder: {blob_name}".encode(), "application/octet-stream"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seed_dir = Path(__file__).resolve().parent
    with open(seed_dir / "tasks.json") as f:
        tasks = json.load(f)

    # Extraer todos los blob names únicos
    pattern = r"https://sp1bpmstorage\.blob\.core\.windows\.net/documentos/([^\s\"]+)"
    blobs = set()

    for t in tasks:
        fd = t.get("formData") or {}
        for val in fd.values():
            if isinstance(val, str) and "blob.core.windows.net" in val:
                match = re.search(pattern, val)
                if match:
                    blobs.add(match.group(1))

    logger.info("Encontrados %d blobs únicos en formData de tasks.", len(blobs))

    if args.dry_run:
        for b in sorted(blobs)[:20]:
            logger.info("  [DRY] %s", b)
        if len(blobs) > 20:
            logger.info("  ... y %d más", len(blobs) - 20)
        return

    # Conectar a Azure
    client = BlobServiceClient.from_connection_string(CONN_STR)
    uploaded = 0
    skipped = 0

    for blob_name in sorted(blobs):
        # Verificar si ya existe
        blob_client = client.get_blob_client(container=CONTAINER, blob=blob_name)
        try:
            blob_client.get_blob_properties()
            skipped += 1
            continue  # ya existe, no sobreescribir
        except Exception:
            pass  # no existe, crear

        contenido, mime = generar_contenido(blob_name)
        blob_client.upload_blob(
            contenido,
            overwrite=False,
            content_settings=ContentSettings(content_type=mime),
        )
        uploaded += 1

        if uploaded % 50 == 0:
            logger.info("  ... %d/%d subidos", uploaded, len(blobs))

    logger.info("✓ Completo: %d subidos, %d ya existían.", uploaded, skipped)


if __name__ == "__main__":
    main()
