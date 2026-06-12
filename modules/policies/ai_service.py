"""
Generación de diagramas UML con IA.
Llama directamente al generador integrado (antes era proxy HTTP a sp1-ai).
"""
import logging

from core.exceptions import AiServiceException
from modules.intelligence.diagram.generator import generate_diagram as _generate
from modules.intelligence.diagram.models import GenerateRequest

logger = logging.getLogger(__name__)


async def generate_diagram(instruccion: str, version_id: str) -> dict:
    try:
        request = GenerateRequest(
            instruccion=instruccion,
            version_id=version_id,
        )
        result = await _generate(request)
        return result.model_dump()
    except ValueError as e:
        logger.warning("Error de validación al generar diagrama: %s", e)
        raise AiServiceException(f"Error de validación: {e}")
    except ConnectionError as e:
        logger.error("LLM no disponible: %s", e)
        raise AiServiceException(f"Servicio de IA no disponible: {e}")
    except Exception as e:
        logger.error("Error inesperado generando diagrama: %s", e)
        raise AiServiceException(f"Error generando diagrama: {e}")
