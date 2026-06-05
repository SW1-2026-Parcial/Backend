import json
import re
import asyncio
import logging
from functools import partial
from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError
from config import get_settings
from modules.intelligence.diagram.models import GenerateRequest, GenerateResponse
from modules.intelligence.diagram.prompts import build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)

_client = None
_MAX_RETRIES        = 3
_DEFAULT_RETRY_WAIT = 15


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
    return _client


def _parse_retry_seconds(error_msg: str) -> float:
    """Extrae el tiempo de espera sugerido por la API del mensaje de error 429."""
    match = re.search(r"retry[_ ]in\s+([\d.]+)s", error_msg, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return _DEFAULT_RETRY_WAIT


def _extract_json(raw: str) -> str:
    """Extrae el JSON del markdown si el LLM lo envuelve en bloques de código."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw


def _call_llm_sync(user_prompt: str) -> str:
    """
    Llamada síncrona al LLM con retry para rate limiting.
    Retorna el contenido texto de la respuesta.
    Lanza ConnectionError si el servicio no está disponible tras todos los intentos.
    """
    last_error = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            settings = get_settings()
            response = _get_client().chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://localhost:8080",
                    "X-OpenRouter-Title": "SP1-BPM-Backend",
                },
                model=settings.openrouter_model,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            last_error = e
            wait = _parse_retry_seconds(str(e))
            logger.warning("429 rate limit (intento %d/%d). Reintentando en %.1fs...",
                           attempt, _MAX_RETRIES, wait)
            if attempt < _MAX_RETRIES:
                import time
                time.sleep(wait)
                continue
            raise ConnectionError(f"Rate limit agotado tras {_MAX_RETRIES} intentos") from e

        except APIConnectionError as e:
            logger.error("Error de conexión con OpenRouter: %s", e)
            raise ConnectionError("No se pudo conectar con el servicio de IA") from e

        except APIStatusError as e:
            logger.error("Error de API OpenRouter [%d]: %s", e.status_code, e.message)
            raise ConnectionError(f"Error del servicio de IA: {e.status_code}") from e

    raise ConnectionError(f"LLM no disponible tras {_MAX_RETRIES} intentos")


async def generate_diagram(request: GenerateRequest) -> GenerateResponse:
    """
    Genera un diagrama UML a partir de la instrucción en lenguaje natural.
    Ejecuta la llamada síncrona al LLM en un threadpool para no bloquear el event loop.
    """
    user_prompt = build_user_prompt(request)

    # run_in_executor: corre la función síncrona en el default ThreadPoolExecutor de asyncio.
    # Esto libera el event loop mientras espera la respuesta del LLM.
    loop = asyncio.get_event_loop()
    raw_content = await loop.run_in_executor(
        None,
        partial(_call_llm_sync, user_prompt)
    )

    try:
        raw_json = _extract_json(raw_content)
        data = json.loads(raw_json)
        return GenerateResponse(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error("Respuesta del LLM no es JSON válido: %.200s", raw_content)
        raise ValueError(f"El LLM retornó una respuesta inválida: {e}") from e
