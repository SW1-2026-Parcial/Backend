"""
Métricas del sistema: bottlenecks y performance.
Equivale a MetricasServiceImpl.java.
"""
from datetime import datetime, timezone
from collections import defaultdict
from models.tramite_event import TramiteEvent, TramiteEventType
from models.tramite import Tramite, EstadoTramite


async def get_bottlenecks() -> list[dict]:
    """
    Calcula tiempo promedio por nodo sumando intervalos entre NODE_ENTERED y TASK_COMPLETED.
    Devuelve lista ordenada de mayor a menor tiempo promedio.
    """
    events = await TramiteEvent.find(
        {"tipo": {"$in": [TramiteEventType.NODE_ENTERED.value, TramiteEventType.TASK_COMPLETED.value]}}
    ).sort("+timestamp").to_list()

    # Agrupar por tramiteId → nodeId → tiempos
    # Estructura: {(tramiteId, nodeId): [(entered_ts, completed_ts), ...]}
    entered: dict[tuple, datetime] = {}
    durations: dict[str, list[float]] = defaultdict(list)

    for ev in events:
        key = (ev.tramiteId, ev.nodeId)
        if ev.tipo == TramiteEventType.NODE_ENTERED:
            entered[key] = ev.timestamp
        elif ev.tipo == TramiteEventType.TASK_COMPLETED and key in entered:
            delta = (ev.timestamp - entered.pop(key)).total_seconds()
            if delta >= 0:
                durations[ev.nodeId].append(delta)

    result = []
    for node_id, times in durations.items():
        avg = sum(times) / len(times)
        result.append({
            "nodeId": node_id,
            "avgDurationSeconds": round(avg, 2),
            "count": len(times),
        })
    result.sort(key=lambda x: x["avgDurationSeconds"], reverse=True)
    return result


async def get_performance() -> dict:
    """
    Métricas generales: total trámites, completados, activos, tasa de completación.
    """
    total = await Tramite.count()
    completed = await Tramite.find(Tramite.status == EstadoTramite.COMPLETED).count()
    active = await Tramite.find(Tramite.status == EstadoTramite.ACTIVE).count()
    rejected = await Tramite.find(Tramite.status == EstadoTramite.REJECTED).count()
    cancelled = await Tramite.find(Tramite.status == EstadoTramite.CANCELLED).count()

    # Tiempo promedio de completación
    completed_tramites = await Tramite.find(
        Tramite.status == EstadoTramite.COMPLETED,
        Tramite.startedAt != None,
        Tramite.completedAt != None,
    ).to_list()

    avg_completion_seconds = None
    if completed_tramites:
        deltas = [
            (t.completedAt - t.startedAt).total_seconds()
            for t in completed_tramites
            if t.startedAt and t.completedAt
        ]
        if deltas:
            avg_completion_seconds = round(sum(deltas) / len(deltas), 2)

    return {
        "total": total,
        "active": active,
        "completed": completed,
        "rejected": rejected,
        "cancelled": cancelled,
        "completionRate": round(completed / total * 100, 1) if total else 0,
        "avgCompletionSeconds": avg_completion_seconds,
    }
