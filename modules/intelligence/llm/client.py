"""
LLM Service — cliente directo a OpenRouter (compatible OpenAI SDK).
Reemplaza la dependencia de sp1-ai para llamadas LLM.
"""
import json
import re
import logging
from typing import Optional

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
    return _client


def _extract_json(raw: str) -> str:
    """Extrae JSON de bloques de codigo markdown si el LLM lo envuelve."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Intentar encontrar JSON suelto
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return match.group(0)
    return raw


async def chat_completion(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """
    Envía un chat completion a OpenRouter y retorna el texto de respuesta.
    `history` es una lista opcional de mensajes previos [{"role": ..., "content": ...}].
    """
    settings = get_settings()
    client = _get_client()

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers={
                "HTTP-Referer": "http://localhost:8080",
                "X-OpenRouter-Title": "SP1-BPM-Backend",
            },
        )
        content = response.choices[0].message.content
        logger.debug("LLM response (%.100s...)", content)
        return content
    except Exception as e:
        logger.error("Error llamando a OpenRouter: %s", e)
        raise


async def chat_completion_json(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    temperature: float = 0.2,
) -> dict:
    """
    Igual que chat_completion pero parsea la respuesta como JSON.
    Lanza ValueError si el LLM no retorna JSON válido.
    """
    raw = await chat_completion(system_prompt, user_message, history, temperature)
    try:
        json_str = _extract_json(raw)
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("LLM no retornó JSON válido: %.300s", raw)
        raise ValueError(f"Respuesta del LLM no es JSON válido: {e}") from e
