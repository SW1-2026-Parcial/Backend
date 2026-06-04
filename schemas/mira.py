"""Schemas de respuesta para los endpoints MIRA."""
from typing import List, Optional, Any
from pydantic import BaseModel


class NivelRiesgo(str):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


# ── Predicción de ruta ────────────────────────────────────────────────────────

class PasoRuta(BaseModel):
    nodeId: str
    etiqueta: str
    tipoNodo: str
    tiempoEstimadoHoras: float
    departamentoId: Optional[str] = None


class PrediccionRutaResponse(BaseModel):
    tramiteId: str
    rutaOptima: List[PasoRuta]
    duracionTotalEstimadaHoras: float
    confianza: float          # 0.0 – 1.0
    explicacion: str


# ── Análisis de riesgo de demora ──────────────────────────────────────────────

class RiesgoItem(BaseModel):
    tramiteId: str
    ticketNumber: Optional[str] = None
    probabilidadDemora: float   # 0.0 – 1.0
    nivelRiesgo: str            # BAJO | MEDIO | ALTO | CRITICO
    factores: List[str]
    horasTranscurridas: float
    horasEstimadasRestantes: float


class RiesgoResponse(BaseModel):
    tramites: List[RiesgoItem]
    resumen: dict               # contadores por nivelRiesgo


# ── Detección de anomalías ────────────────────────────────────────────────────

class AnomaliaItem(BaseModel):
    tramiteId: str
    ticketNumber: Optional[str] = None
    tipo: str                   # TIEMPO_EXCESIVO | SIN_ASIGNAR | BUCLE_DETECTADO | PRIORIDAD_IGNORADA
    descripcion: str
    gravedad: str               # INFO | WARNING | ERROR
    nodeId: Optional[str] = None
    timestamp: Optional[str] = None


class AnomaliaResponse(BaseModel):
    anomalias: List[AnomaliaItem]
    total: int


# ── Priorización de recursos ──────────────────────────────────────────────────

class TareaPriorizada(BaseModel):
    taskId: str
    tramiteId: str
    ticketNumber: Optional[str] = None
    nodeId: str
    etiquetaNodo: str
    prioridadMIRA: int          # 1 = más urgente
    scoreUrgencia: float
    factores: List[str]
    assignedTo: Optional[str] = None
    departamentoId: Optional[str] = None


class PriorizacionResponse(BaseModel):
    tareas: List[TareaPriorizada]
    total: int


# ── Dashboard consolidado ─────────────────────────────────────────────────────

class MiraDashboardResponse(BaseModel):
    resumenRiesgos: dict
    totalAnomalias: int
    totalTareasPendientes: int
    bottleneckTopNodo: Optional[str] = None
    scoreRiesgoGlobal: float    # 0.0 – 1.0, promedio ponderado
    alertas: List[dict]
