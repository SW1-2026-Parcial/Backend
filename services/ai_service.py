"""
Proxy hacia sp1-ai para generación de diagramas UML con IA.
Usa el http_client singleton con connection pooling.
"""
import logging
import httpx

from config import get_settings
from core.exceptions import AiServiceException
from core.http_client import http_client

logger = logging.getLogger(__name__)


async def generate_diagram(instruccion: str, version_id: str) -> dict:
    settings = get_settings()
    url = f"{settings.ai_service_url}/generate"
    payload = {"instruccion": instruccion, "version_id": version_id}
    try:
        response = await http_client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout llamando a sp1-ai")
        raise AiServiceException("Timeout: el servicio de IA no respondió a tiempo")
    except httpx.HTTPStatusError as e:
        logger.error("sp1-ai respondió %d: %s", e.response.status_code, e.response.text)
        raise AiServiceException(f"sp1-ai error {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error("No se pudo conectar a sp1-ai: %s", e)
        raise AiServiceException("No se pudo conectar al servicio de IA")
