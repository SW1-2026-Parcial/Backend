from fastapi import APIRouter, Depends
from core.security import require_admin_or_supervisor
from modules.metrics.service import get_bottlenecks, get_performance

router = APIRouter(prefix="/api/metrics", tags=["metricas"])


@router.get("/bottlenecks", dependencies=[Depends(require_admin_or_supervisor)])
async def bottlenecks():
    """Nodos con mayor tiempo promedio de ejecución (cuellos de botella)."""
    return await get_bottlenecks()


@router.get("/performance", dependencies=[Depends(require_admin_or_supervisor)])
async def performance():
    """Métricas globales: total trámites, tasa de completación, tiempo promedio."""
    return await get_performance()
