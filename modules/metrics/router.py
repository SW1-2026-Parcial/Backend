from typing import Optional
from fastapi import APIRouter, Depends, Query
from core.security import require_admin_or_supervisor
from modules.metrics.service import get_bottlenecks, get_performance

router = APIRouter(prefix="/api/metrics", tags=["metricas"])


@router.get("/bottlenecks", dependencies=[Depends(require_admin_or_supervisor)])
async def bottlenecks(versionId: Optional[str] = Query(None)):
    """Nodos con mayor tiempo promedio de ejecución (cuellos de botella).
    Acepta ?versionId= para filtrar por versión de política."""
    return await get_bottlenecks(version_id=versionId)


@router.get("/performance", dependencies=[Depends(require_admin_or_supervisor)])
async def performance(
    versionId: Optional[str] = Query(None),
    desde:     Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    hasta:     Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
):
    """Métricas globales: total trámites, tasa de completación, tiempo promedio.
    Acepta ?versionId=, ?desde= y ?hasta= para filtrar."""
    return await get_performance(version_id=versionId, desde=desde, hasta=hasta)
