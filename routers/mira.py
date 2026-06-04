"""
MIRA — Motor Inteligente de Reconocimiento y Análisis.
Expone las 4 capacidades analíticas + dashboard consolidado.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from core.security import require_admin_or_supervisor
from services.mira_service import (
    predecir_ruta,
    analizar_riesgo,
    detectar_anomalias,
    priorizar_recursos,
    get_dashboard,
)
from schemas.mira import (
    PrediccionRutaResponse,
    RiesgoResponse,
    AnomaliaResponse,
    PriorizacionResponse,
    MiraDashboardResponse,
)

router = APIRouter(
    prefix="/api/mira",
    tags=["mira"],
    dependencies=[Depends(require_admin_or_supervisor)],
)


@router.get("/dashboard", response_model=MiraDashboardResponse)
async def dashboard():
    """
    Dashboard consolidado MIRA: resumen de riesgos, anomalías, tareas priorizadas
    y score de riesgo global del sistema.
    """
    return await get_dashboard()


@router.get("/predict-route/{tramite_id}", response_model=PrediccionRutaResponse)
async def predict_route(tramite_id: str):
    """
    Predice la ruta óptima para un trámite en ejecución,
    estimando tiempos por nodo basándose en el histórico real.
    """
    result = await predecir_ruta(tramite_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trámite no encontrado")
    return result


@router.get("/risk-analysis", response_model=RiesgoResponse)
async def risk_analysis():
    """
    Analiza todos los trámites activos y calcula su probabilidad de demora
    usando heurísticas sobre tiempo transcurrido, prioridad y tareas sin asignar.
    """
    return await analizar_riesgo()


@router.get("/anomalies", response_model=AnomaliaResponse)
async def anomalies():
    """
    Detecta anomalías operativas: tareas sin asignar por tiempo excesivo,
    nodos lentos respecto al histórico, y trámites prioritarios estancados.
    """
    return await detectar_anomalias()


@router.get("/resource-priority", response_model=PriorizacionResponse)
async def resource_priority():
    """
    Devuelve las tareas pendientes ordenadas por urgencia MIRA (1 = más urgente),
    combinando prioridad del trámite, antigüedad y anomalías detectadas.
    """
    return await priorizar_recursos()
