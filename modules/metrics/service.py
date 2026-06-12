"""
Métricas del sistema: bottlenecks y performance.
Equivale a MetricasServiceImpl.java.
"""
from datetime import datetime, timezone
from collections import defaultdict
from models.tramite_event import TramiteEvent, TramiteEventType
from models.tramite import Tramite, EstadoTramite
from models.nodo import Nodo


async def get_bottlenecks(version_id: str | None = None) -> list[dict]:
    """
    Calcula tiempo promedio por nodo sumando intervalos entre NODE_ENTERED y TASK_COMPLETED.
    Filtra por versión si se provee version_id: solo considera trámites de esa versión.
    Devuelve lista ordenada de mayor a menor tiempo promedio con etiqueta del nodo y ranking.
    """
    # Si hay version_id, primero obtener los tramiteIds de esa versión
    tramite_ids: list[str] | None = None
    if version_id:
        tramites_version = await Tramite.find(
            Tramite.versionPoliticaId == version_id
        ).to_list()
        tramite_ids = [str(t.id) for t in tramites_version]
        if not tramite_ids:
            return []  # sin trámites para esta versión → sin bottlenecks

    from beanie.operators import In
    event_filter = [
        In(TramiteEvent.tipo, [TramiteEventType.NODE_ENTERED, TramiteEventType.TASK_COMPLETED])
    ]
    if tramite_ids is not None:
        event_filter.append(In(TramiteEvent.tramiteId, tramite_ids))

    events = await TramiteEvent.find(*event_filter).sort("+timestamp").to_list()

    # Agrupar por tramiteId → nodeId → tiempos
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

    # Cargar etiquetas de nodos en una sola query
    node_ids = list(durations.keys())
    nodo_query = {"nodoId": {"$in": node_ids}}
    if version_id:
        nodo_query["versionPoliticaId"] = version_id  # type: ignore[assignment]
    nodos = await Nodo.find(nodo_query).to_list()
    etiqueta_map: dict[str, str] = {n.nodoId: n.etiqueta for n in nodos}

    result = []
    for node_id, times in durations.items():
        avg_s = sum(times) / len(times)
        result.append({
            "nodeId": node_id,
            "etiqueta": etiqueta_map.get(node_id, node_id),   # fallback al ID si no se encontró
            "avgDurationMs": round(avg_s * 1000),              # frontend trabaja en ms
            "count": len(times),
        })

    result.sort(key=lambda x: x["avgDurationMs"], reverse=True)

    # Agregar ranking (1 = más lento)
    for i, item in enumerate(result):
        item["ranking"] = i + 1

    return result


async def get_performance(
    version_id: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> dict:
    """
    Métricas generales: total trámites, completados, activos, tasa de completación.
    Acepta version_id, desde y hasta (ISO date strings) para filtrar.
    """
    # Construir filtros Beanie tipados (no raw dict) para que los enums se resuelvan bien
    version_filter = []
    if version_id:
        version_filter = [Tramite.versionPoliticaId == version_id]
    if desde:
        try:
            dt_desde = datetime.fromisoformat(desde).replace(tzinfo=timezone.utc)
            version_filter.append(Tramite.startedAt >= dt_desde)
        except ValueError:
            pass
    if hasta:
        try:
            dt_hasta = datetime.fromisoformat(hasta).replace(tzinfo=timezone.utc)
            version_filter.append(Tramite.startedAt <= dt_hasta)
        except ValueError:
            pass

    total     = await Tramite.find(*version_filter).count()
    completed = await Tramite.find(*version_filter, Tramite.status == EstadoTramite.COMPLETED).count()
    active    = await Tramite.find(*version_filter, Tramite.status == EstadoTramite.ACTIVE).count()
    rejected  = await Tramite.find(*version_filter, Tramite.status == EstadoTramite.REJECTED).count()
    cancelled = await Tramite.find(*version_filter, Tramite.status == EstadoTramite.CANCELLED).count()

    # Tiempo promedio de completación en ms
    completed_tramites = await Tramite.find(
        *version_filter,
        Tramite.status == EstadoTramite.COMPLETED,
    ).to_list()

    avg_completion_ms: float | None = None
    if completed_tramites:
        deltas = [
            (t.completedAt - t.startedAt).total_seconds() * 1000
            for t in completed_tramites
            if t.startedAt and t.completedAt
        ]
        if deltas:
            avg_completion_ms = round(sum(deltas) / len(deltas))

    return {
        "total":           total,
        "active":          active,
        "completed":       completed,
        "rejected":        rejected,
        "cancelled":       cancelled,
        "completionRate":  round(completed / total * 100, 1) if total else 0,
        "avgCompletionMs": avg_completion_ms,   # ms — frontend usa formatMs()
    }
