"""
Agente Conversacional BPM — Ciclo 2.
Endpoint PÚBLICO (sin JWT) — diseñado para la app móvil del usuario final.
El usuario escribe (texto o voz transcrita en frontend) y el agente identifica
la política, recopila datos y permite iniciar un trámite.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from beanie import PydanticObjectId

from modules.intelligence.chat.agent_service import chat, clear_session
from models.politica import Politica, EstadoPolitica
from models.version_politica import VersionPolitica
from models.tramite import Tramite, EstadoTramite, Prioridad
from modules.engine.ticket_service import generate_ticket
from modules.engine.workflow.workflow_engine import workflow_engine
from core.exceptions import NotFoundException, BusinessException

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


class IniciarTramiteRequest(BaseModel):
    politicaId: str
    camposRecopilados: dict = {}
    fcmToken: Optional[str] = None


class IniciarTramiteResponse(BaseModel):
    tramiteId: str
    ticketNumber: str
    politicaId: str
    status: str


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


@router.post("/iniciar-tramite", response_model=IniciarTramiteResponse)
async def agent_iniciar_tramite(body: IniciarTramiteRequest):
    """
    Crea un trámite a partir de los datos recopilados por el agente.
    Endpoint PÚBLICO — no requiere autenticación (app móvil del cliente).
    """
    versions = await VersionPolitica.find(
        VersionPolitica.politicaId == body.politicaId,
        VersionPolitica.estado == EstadoPolitica.PUBLISHED,
    ).sort("-numeroVersion").limit(1).to_list()

    if not versions:
        raise BusinessException("No hay versión publicada para esta política")

    version = versions[0]
    ticket = await generate_ticket()

    tramite = Tramite(
        politicaId=body.politicaId,
        versionPoliticaId=str(version.id),
        status=EstadoTramite.ACTIVE,
        prioridad=Prioridad.MEDIUM,
        initiatedBy="mobile_agent",
        ticketNumber=ticket,
        startedAt=datetime.now(timezone.utc),
        fcmToken=body.fcmToken,
    )
    await tramite.insert()

    await workflow_engine.start_tramite(tramite, actor_id="mobile_agent")

    tramite = await Tramite.get(tramite.id)
    return IniciarTramiteResponse(
        tramiteId=str(tramite.id),
        ticketNumber=tramite.ticketNumber,
        politicaId=tramite.politicaId,
        status=tramite.status.value,
    )


@router.post("/clear-session")
async def agent_clear_session(body: AgentChatRequest):
    """Limpia el historial de conversación de una sesión."""
    if body.sessionId:
        clear_session(body.sessionId)
    return {"ok": True}
