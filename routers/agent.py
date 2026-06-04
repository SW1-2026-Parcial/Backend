"""
Agente Conversacional BPM — Ciclo 2.
Endpoint PÚBLICO (sin JWT) — diseñado para la app móvil del usuario final.
El usuario escribe (texto o voz transcrita en frontend) y el agente identifica
la política, recopila datos y permite iniciar un trámite.
"""
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.agent_service import chat, clear_session

router = APIRouter(prefix="/api/agent", tags=["agente"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentChatRequest(BaseModel):
    mensaje: str
    sessionId: Optional[str] = None


class AgentChatResponse(BaseModel):
    mensaje: str
    politicaIdentificada: Optional[str] = None
    politicaNombre: Optional[str] = None
    camposRecopilados: dict = {}
    camposFaltantes: list[str] = []
    listoParaIniciar: bool = False
    sugerencias: list[str] = []
    sessionId: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest):
    """
    Envía un mensaje de texto al agente conversacional.
    Endpoint PÚBLICO — no requiere autenticación (app móvil del cliente).
    Si no se envía sessionId, se crea una sesión nueva.
    El agente identifica la política, recopila datos y guía al usuario.
    """
    session_id = body.sessionId or str(uuid.uuid4())
    result = await chat(session_id=session_id, user_message=body.mensaje)
    return AgentChatResponse(**result)


@router.post("/clear-session")
async def agent_clear_session(body: AgentChatRequest):
    """Limpia el historial de conversación de una sesión."""
    if body.sessionId:
        clear_session(body.sessionId)
    return {"ok": True}
