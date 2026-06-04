"""
Agente Conversacional BPM — Ciclo 2.
Mantiene contexto por sesión, identifica políticas y recopila datos para iniciar trámites.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from models.politica import Politica, EstadoPolitica
from models.version_politica import VersionPolitica
from models.nodo import Nodo
from models.departamento import Departamento
from services.llm_service import chat_completion, chat_completion_json

logger = logging.getLogger(__name__)

# ── Historial en memoria por sesión ───────────────────────────────────────────
# En producción esto iría a Redis/MongoDB. Para el parcial, dict en memoria basta.
_sessions: dict[str, list[dict]] = {}

MAX_HISTORY = 20  # máximo de mensajes por sesión


def _get_history(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


def _add_to_history(session_id: str, role: str, content: str):
    history = _get_history(session_id)
    history.append({"role": role, "content": content})
    # Trimming: mantener solo los últimos MAX_HISTORY mensajes
    if len(history) > MAX_HISTORY:
        _sessions[session_id] = history[-MAX_HISTORY:]


# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """Eres un asistente virtual del Sistema BPM SP1. Tu rol es ayudar a los usuarios a:
1. Identificar qué trámite/política necesitan iniciar
2. Recopilar los datos requeridos por el formulario del primer nodo
3. Guiar al usuario paso a paso

POLÍTICAS DISPONIBLES:
{politicas_context}

INSTRUCCIONES:
- Responde siempre en español, de forma concisa y amable.
- Si el usuario describe su necesidad, identifica la política más adecuada.
- Una vez identificada la política, pregunta uno por uno los campos requeridos del formulario.
- Cuando tengas todos los campos completos, responde con un JSON indicando que está listo.
- Si no entiendes, pide aclaraciones.
- Nunca inventes políticas que no estén en la lista.

FORMATO DE RESPUESTA:
Siempre responde con un JSON con esta estructura:
{{
  "mensaje": "texto de respuesta al usuario",
  "politicaIdentificada": "id_de_la_politica o null",
  "politicaNombre": "nombre legible o null",
  "camposRecopilados": {{"campo1": "valor1", ...}},
  "camposFaltantes": ["campo2", "campo3"],
  "listoParaIniciar": false,
  "sugerencias": ["opción 1", "opción 2"]
}}
"""


async def _build_policies_context() -> str:
    """Construye el contexto de políticas publicadas con sus formularios."""
    # Obtener políticas activas
    politicas = await Politica.find(Politica.estado == EstadoPolitica.PUBLISHED).to_list()
    if not politicas:
        return "No hay políticas publicadas actualmente."

    # Obtener versiones publicadas
    lines = []
    for pol in politicas:
        # Buscar última versión publicada
        versions = await VersionPolitica.find(
            VersionPolitica.politicaId == str(pol.id),
            VersionPolitica.estado == EstadoPolitica.PUBLISHED,
        ).sort("-numeroVersion").limit(1).to_list()

        if not versions:
            continue
        ver = versions[0]

        # Obtener nodos ACTIVITY del primer paso (recepcion)
        nodos = await Nodo.find(
            Nodo.versionPoliticaId == str(ver.id),
            Nodo.tipoNodo == "ACTIVITY",
        ).to_list()

        # Tomar el primer nodo activity (recepcion) que tiene formulario
        primer_nodo = None
        for n in nodos:
            if n.formulario:
                primer_nodo = n
                break

        campos_str = ""
        if primer_nodo and primer_nodo.formulario:
            campos = []
            for c in primer_nodo.formulario:
                req = " (OBLIGATORIO)" if c.requerido else " (opcional)"
                campos.append(f"    - {c.nombre}: {c.etiqueta} [{c.tipo}]{req}")
            campos_str = "\n".join(campos)

        lines.append(
            f"- **{pol.nombre}** (ID: {str(pol.id)})\n"
            f"  Descripción: {pol.descripcion or 'Sin descripción'}\n"
            f"  Campos del formulario inicial:\n{campos_str}"
        )

    return "\n\n".join(lines)


# ── Chat principal ────────────────────────────────────────────────────────────

async def chat(session_id: str, user_message: str) -> dict:
    """
    Procesa un mensaje del usuario y retorna la respuesta del agente.
    Mantiene historial por sesión.
    """
    # Construir contexto de políticas (cacheado por sesión en primera llamada)
    politicas_context = await _build_policies_context()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(politicas_context=politicas_context)

    # Agregar mensaje del usuario al historial
    _add_to_history(session_id, "user", user_message)
    history = _get_history(session_id)

    try:
        result = await chat_completion_json(
            system_prompt=system_prompt,
            user_message=user_message,
            history=history[:-1],  # el último ya es el user_message actual
            temperature=0.3,
        )

        # Guardar respuesta del asistente en el historial
        assistant_msg = result.get("mensaje", "")
        _add_to_history(session_id, "assistant", assistant_msg)

        return {
            "mensaje": result.get("mensaje", "No pude procesar tu solicitud."),
            "politicaIdentificada": result.get("politicaIdentificada"),
            "politicaNombre": result.get("politicaNombre"),
            "camposRecopilados": result.get("camposRecopilados", {}),
            "camposFaltantes": result.get("camposFaltantes", []),
            "listoParaIniciar": result.get("listoParaIniciar", False),
            "sugerencias": result.get("sugerencias", []),
            "sessionId": session_id,
        }

    except ValueError:
        # Fallback si el LLM no retorna JSON válido
        fallback = await chat_completion(
            system_prompt="Eres un asistente BPM. Responde en español de forma breve.",
            user_message=user_message,
            history=history[:-1],
        )
        _add_to_history(session_id, "assistant", fallback)
        return {
            "mensaje": fallback,
            "politicaIdentificada": None,
            "politicaNombre": None,
            "camposRecopilados": {},
            "camposFaltantes": [],
            "listoParaIniciar": False,
            "sugerencias": [],
            "sessionId": session_id,
        }

    except Exception as e:
        logger.error("Error en agent_service.chat: %s", e)
        return {
            "mensaje": "Lo siento, ocurrió un error al procesar tu mensaje. Intenta de nuevo.",
            "politicaIdentificada": None,
            "politicaNombre": None,
            "camposRecopilados": {},
            "camposFaltantes": [],
            "listoParaIniciar": False,
            "sugerencias": [],
            "sessionId": session_id,
        }


def clear_session(session_id: str) -> None:
    """Limpia el historial de una sesión."""
    _sessions.pop(session_id, None)
