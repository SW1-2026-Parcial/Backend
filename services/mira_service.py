"""
MIRA — Motor Inteligente de Reconocimiento y Análisis.
Heurísticas basadas en reglas sobre los datos reales de MongoDB.
Día 3 añadirá la capa TensorFlow encima de estas mismas consultas.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Optional

from models.tramite import Tramite, EstadoTramite, Prioridad
from models.task import Task, EstadoTask
from models.tramite_event import TramiteEvent, TramiteEventType
from models.nodo import Nodo
from services.metricas_service import get_bottlenecks


# ── Umbrales configurables ────────────────────────────────────────────────────

UMBRAL_DEMORA_MEDIO_H   = 4.0    # horas activo sin avanzar → riesgo MEDIO
UMBRAL_DEMORA_ALTO_H    = 12.0   # horas → ALTO
UMBRAL_DEMORA_CRITICO_H = 24.0   # horas → CRITICO
UMBRAL_SIN_ASIGNAR_H    = 2.0    # tarea sin asignar → anomalía
UMBRAL_TIEMPO_NODO_X    = 3.0    # multiplicador vs promedio histórico → anomalía


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nivel_riesgo(prob: float) -> str:
    if prob >= 0.75:  return "CRITICO"
    if prob >= 0.50:  return "ALTO"
    if prob >= 0.25:  return "MEDIO"
    return "BAJO"


def _score_prioridad(tramite: Tramite, horas_activo: float) -> float:
    """Score normalizado 0-1. Mayor = más urgente."""
    pesos = {
        Prioridad.CRITICAL: 1.0,
        Prioridad.URGENT:   0.95,
        Prioridad.HIGH:     0.70,
        Prioridad.MEDIUM:   0.40,
        Prioridad.LOW:      0.15,
    }
    base = pesos.get(tramite.prioridad, 0.40)
    # Penalizar por antigüedad (máx 24h añade 0.3 al score)
    penalizacion = min(horas_activo / 24.0, 1.0) * 0.30
    return min(base + penalizacion, 1.0)


async def _promedios_por_nodo() -> dict[str, float]:
    """Tiempo promedio histórico por nodeId (segundos)."""
    events = await TramiteEvent.find(
        {"tipo": {"$in": [TramiteEventType.NODE_ENTERED.value, TramiteEventType.TASK_COMPLETED.value]}}
    ).sort("+timestamp").to_list()

    entered: dict = {}
    durations: dict[str, list] = defaultdict(list)
    for ev in events:
        key = (ev.tramiteId, ev.nodeId)
        if ev.tipo == TramiteEventType.NODE_ENTERED:
            entered[key] = ev.timestamp
        elif ev.tipo == TramiteEventType.TASK_COMPLETED and key in entered:
            delta = (ev.timestamp - entered.pop(key)).total_seconds()
            if delta >= 0:
                durations[str(ev.nodeId)].append(delta)

    return {nid: sum(ts) / len(ts) for nid, ts in durations.items() if ts}


# ── 1. Predicción de ruta óptima ─────────────────────────────────────────────

async def predecir_ruta(tramite_id: str) -> dict:
    """
    Construye la ruta más probable desde el nodo actual hasta END,
    estimando tiempos basándose en el histórico de la versión de política.
    Para DECISION nodes elige el ramal más frecuente en el histórico.
    """
    tramite = await Tramite.find_one({"_id": {"$oid": tramite_id}})
    if not tramite:
        # Buscar por string id
        from beanie import PydanticObjectId
        tramite = await Tramite.get(PydanticObjectId(tramite_id))
    if not tramite:
        return {}

    promedios = await _promedios_por_nodo()

    # Cargar todos los nodos de esta versión
    nodos = await Nodo.find(Nodo.versionPoliticaId == tramite.versionPoliticaId).to_list()
    nodos_map = {n.nodoId: n for n in nodos}

    # BFS desde nodo actual hasta END
    inicio_ids = tramite.currentNodeIds or []
    if not inicio_ids and nodos:
        # Tomar el nodo START si el trámite aún no avanzó
        starts = [n for n in nodos if n.tipoNodo.value == "START"]
        inicio_ids = [starts[0].nodoId] if starts else []

    visitados = set()
    ruta: list[dict] = []
    cola = list(inicio_ids)

    while cola:
        nodo_id = cola.pop(0)
        if nodo_id in visitados:
            continue
        visitados.add(nodo_id)

        nodo = nodos_map.get(nodo_id)
        if not nodo:
            continue

        tiempo_est = promedios.get(nodo_id, 1.0) / 3600.0  # convertir a horas
        ruta.append({
            "nodeId": nodo_id,
            "etiqueta": nodo.etiqueta,
            "tipoNodo": nodo.tipoNodo.value,
            "tiempoEstimadoHoras": round(tiempo_est, 2),
            "departamentoId": nodo.calleId,
        })

        if nodo.tipoNodo.value == "END":
            break

        # Añadir siguiente(s) a la cola — para DECISION, elegir la rama True
        for salida in nodo.salidas:
            if salida.nodoDestino not in visitados:
                if nodo.tipoNodo.value == "DECISION":
                    if salida.rama:  # ruta "Sí"
                        cola.append(salida.nodoDestino)
                        break
                else:
                    cola.append(salida.nodoDestino)

    duracion_total = sum(p["tiempoEstimadoHoras"] for p in ruta)
    confianza = 0.85 if len(promedios) > 5 else 0.55

    return {
        "tramiteId": tramite_id,
        "rutaOptima": ruta,
        "duracionTotalEstimadaHoras": round(duracion_total, 2),
        "confianza": confianza,
        "explicacion": (
            f"Ruta de {len(ruta)} nodos. Tiempo estimado basado en "
            f"{len(promedios)} históricos de ejecución."
        ),
    }


# ── 2. Análisis de riesgo de demora ──────────────────────────────────────────

async def analizar_riesgo() -> dict:
    """Evalúa cada trámite ACTIVE y calcula probabilidad de demora."""
    now = datetime.now(timezone.utc)
    activos = await Tramite.find(Tramite.status == EstadoTramite.ACTIVE).to_list()

    items = []
    contadores = {"BAJO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}

    for t in activos:
        inicio = t.startedAt or now
        # Hacer timezone-aware si viene sin timezone
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        horas = (now - inicio).total_seconds() / 3600.0
        factores = []

        # Factor 1: tiempo transcurrido
        if horas >= UMBRAL_DEMORA_CRITICO_H:
            prob_base = 0.85
            factores.append(f"Activo hace {horas:.0f}h (supera umbral crítico de {UMBRAL_DEMORA_CRITICO_H}h)")
        elif horas >= UMBRAL_DEMORA_ALTO_H:
            prob_base = 0.60
            factores.append(f"Activo hace {horas:.0f}h (supera umbral alto de {UMBRAL_DEMORA_ALTO_H}h)")
        elif horas >= UMBRAL_DEMORA_MEDIO_H:
            prob_base = 0.35
            factores.append(f"Activo hace {horas:.0f}h (supera umbral medio de {UMBRAL_DEMORA_MEDIO_H}h)")
        else:
            prob_base = 0.10

        # Factor 2: prioridad alta sin avance
        if t.prioridad in (Prioridad.CRITICAL, Prioridad.URGENT) and horas > 1:
            prob_base = min(prob_base + 0.15, 1.0)
            factores.append("Prioridad crítica/urgente con demora detectada")

        # Factor 3: tareas sin asignar
        tareas_sin_asignar = await Task.find(
            Task.tramiteId == str(t.id),
            Task.status == EstadoTask.PENDING,
            Task.assignedTo == None,
        ).count()
        if tareas_sin_asignar:
            prob_base = min(prob_base + 0.10, 1.0)
            factores.append(f"{tareas_sin_asignar} tarea(s) pendiente(s) sin asignar")

        nivel = _nivel_riesgo(prob_base)
        contadores[nivel] += 1
        items.append({
            "tramiteId": str(t.id),
            "ticketNumber": t.ticketNumber,
            "probabilidadDemora": round(prob_base, 3),
            "nivelRiesgo": nivel,
            "factores": factores if factores else ["Sin factores de riesgo detectados"],
            "horasTranscurridas": round(horas, 1),
            "horasEstimadasRestantes": max(0.0, round(UMBRAL_DEMORA_ALTO_H - horas, 1)),
        })

    # Ordenar por probabilidad descendente
    items.sort(key=lambda x: x["probabilidadDemora"], reverse=True)
    return {"tramites": items, "resumen": contadores}


# ── 3. Detección de anomalías ─────────────────────────────────────────────────

async def detectar_anomalias() -> dict:
    """Detecta patrones anómalos en trámites y tareas activos."""
    now = datetime.now(timezone.utc)
    promedios = await _promedios_por_nodo()
    anomalias = []

    # A1: tareas sin asignar por más de UMBRAL_SIN_ASIGNAR_H
    tareas = await Task.find(
        Task.status == EstadoTask.PENDING,
        Task.assignedTo == None,
    ).to_list()
    for t in tareas:
        creado = t.createdAt or now
        if creado.tzinfo is None:
            creado = creado.replace(tzinfo=timezone.utc)
        horas = (now - creado).total_seconds() / 3600.0
        if horas >= UMBRAL_SIN_ASIGNAR_H:
            anomalias.append({
                "tramiteId": t.tramiteId,
                "ticketNumber": None,
                "tipo": "SIN_ASIGNAR",
                "descripcion": f"Tarea en nodo '{t.nodeId}' lleva {horas:.1f}h sin asignar",
                "gravedad": "WARNING" if horas < 6 else "ERROR",
                "nodeId": t.nodeId,
                "timestamp": now.isoformat(),
            })

    # A2: trámites activos con tiempo excesivo respecto al promedio histórico
    activos = await Tramite.find(Tramite.status == EstadoTramite.ACTIVE).to_list()
    for tr in activos:
        for node_id in tr.currentNodeIds:
            avg_s = promedios.get(node_id)
            if not avg_s:
                continue
            # Buscar cuánto lleva en este nodo
            ev_entrada = await TramiteEvent.find_one(
                TramiteEvent.tramiteId == str(tr.id),
                TramiteEvent.nodeId == node_id,
                TramiteEvent.tipo == TramiteEventType.NODE_ENTERED,
            )
            if not ev_entrada:
                continue
            ts = ev_entrada.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            tiempo_actual_s = (now - ts).total_seconds()
            if tiempo_actual_s > avg_s * UMBRAL_TIEMPO_NODO_X:
                anomalias.append({
                    "tramiteId": str(tr.id),
                    "ticketNumber": tr.ticketNumber,
                    "tipo": "TIEMPO_EXCESIVO",
                    "descripcion": (
                        f"Nodo '{node_id}' lleva {tiempo_actual_s/3600:.1f}h "
                        f"(promedio histórico: {avg_s/3600:.1f}h)"
                    ),
                    "gravedad": "WARNING",
                    "nodeId": node_id,
                    "timestamp": now.isoformat(),
                })

    # A3: trámites de prioridad CRITICAL/URGENT sin avance en 1h
    for tr in activos:
        if tr.prioridad not in (Prioridad.CRITICAL, Prioridad.URGENT):
            continue
        inicio = tr.startedAt or now
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        horas = (now - inicio).total_seconds() / 3600.0
        if horas >= 1.0:
            anomalias.append({
                "tramiteId": str(tr.id),
                "ticketNumber": tr.ticketNumber,
                "tipo": "PRIORIDAD_IGNORADA",
                "descripcion": (
                    f"Trámite {tr.prioridad.value} activo hace {horas:.1f}h sin completarse"
                ),
                "gravedad": "ERROR" if horas >= 4 else "WARNING",
                "nodeId": None,
                "timestamp": now.isoformat(),
            })

    return {"anomalias": anomalias, "total": len(anomalias)}


# ── 4. Priorización de recursos ───────────────────────────────────────────────

async def priorizar_recursos() -> dict:
    """
    Ordena las tareas PENDING/IN_PROGRESS por urgencia MIRA,
    combinando prioridad del trámite, tiempo sin asignar y anomalías.
    """
    now = datetime.now(timezone.utc)
    tareas = await Task.find(
        {"status": {"$in": [EstadoTask.PENDING.value, EstadoTask.IN_PROGRESS.value]}}
    ).to_list()

    # Prefetch trámites para evitar N+1
    tramite_ids = list({t.tramiteId for t in tareas})
    from beanie import PydanticObjectId
    tramites_list = []
    for tid in tramite_ids:
        try:
            tr = await Tramite.get(PydanticObjectId(tid))
            if tr:
                tramites_list.append(tr)
        except Exception:
            pass
    tramites_map = {str(tr.id): tr for tr in tramites_list}

    # Prefetch nodos para etiquetas
    nodos = await Nodo.find().to_list()
    nodos_map = {n.nodoId: n for n in nodos}

    scored = []
    for task in tareas:
        tramite = tramites_map.get(task.tramiteId)
        if not tramite:
            continue

        inicio = tramite.startedAt or now
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        horas = (now - inicio).total_seconds() / 3600.0
        score = _score_prioridad(tramite, horas)

        factores = [f"Prioridad trámite: {tramite.prioridad.value}"]
        if not task.assignedTo:
            factores.append("Sin asignar")
            score = min(score + 0.05, 1.0)
        if horas >= UMBRAL_DEMORA_ALTO_H:
            factores.append(f"Trámite retrasado ({horas:.0f}h)")

        nodo = nodos_map.get(task.nodeId)
        etiqueta = nodo.etiqueta if nodo else task.nodeId

        scored.append((score, {
            "taskId": str(task.id),
            "tramiteId": task.tramiteId,
            "ticketNumber": tramite.ticketNumber,
            "nodeId": task.nodeId,
            "etiquetaNodo": etiqueta,
            "scoreUrgencia": round(score, 3),
            "factores": factores,
            "assignedTo": task.assignedTo,
            "departamentoId": task.departamentoId,
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    tareas_priorizadas = []
    for i, (_, item) in enumerate(scored, start=1):
        item["prioridadMIRA"] = i
        tareas_priorizadas.append(item)

    return {"tareas": tareas_priorizadas, "total": len(tareas_priorizadas)}


# ── Dashboard consolidado ─────────────────────────────────────────────────────

async def get_dashboard() -> dict:
    """Agrega los 4 análisis en un único payload para el frontend."""
    riesgo = await analizar_riesgo()
    anomalias = await detectar_anomalias()
    priorizacion = await priorizar_recursos()

    resumen = riesgo["resumen"]
    total_tareas = priorizacion["total"]

    # Score global de riesgo (0-1)
    total_tramites = sum(resumen.values()) or 1
    score_global = (
        resumen.get("CRITICO", 0) * 1.0 +
        resumen.get("ALTO",    0) * 0.67 +
        resumen.get("MEDIO",   0) * 0.33
    ) / total_tramites

    # Top anomalías para alertas rápidas
    alertas = [
        a for a in anomalias["anomalias"]
        if a["gravedad"] == "ERROR"
    ][:5]

    bottlenecks = await get_bottlenecks()
    top_nodo = bottlenecks[0]["nodeId"] if bottlenecks else None

    return {
        "resumenRiesgos": resumen,
        "totalAnomalias": anomalias["total"],
        "totalTareasPendientes": total_tareas,
        "bottleneckTopNodo": top_nodo,
        "scoreRiesgoGlobal": round(min(score_global, 1.0), 3),
        "alertas": alertas,
    }
