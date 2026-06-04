#!/usr/bin/env python3
"""
Seed data generator for swp1_db — fresh repopulation (except usuarios).
Produces 5 JSON files ready for MongoDB Compass insertMany / mongoimport:
  nodos.json, tramites.json, tasks.json, tramite_events.json, counters.json

Usage:
  cd seed/
  python3 gen_seed_data.py

Then in Compass: open each collection → Add data → Insert document (paste array).
Or via mongosh:
  use swp1_db
  db.nodos.insertMany( <paste nodos.json content> )
  ... etc.
"""

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Reproducible output ────────────────────────────────────────────────────────
random.seed(42)

# ── Known IDs (already in DB) ──────────────────────────────────────────────────
ACTORS = [
    "69f0d29b1665e461c0cf689c",  # admin
    "69f1d9079bac949c125ee967",  # pedro
]

POLITICA_IDS = [f"cc100000000000000000000{i}" for i in range(1, 6)]
VERSION_IDS  = [f"cc200000000000000000000{i}" for i in range(1, 6)]

DEPT = {
    "sistemas":    "dd1000000000000000000001",
    "compras":     "dd1000000000000000000002",
    "rrhh":        "dd1000000000000000000003",
    "operaciones": "dd1000000000000000000004",
    "recepcion":   "dd1000000000000000000005",
}

# Processing dept (activity nodes after decision) per policy index
POL_PROC_DEPT = [
    DEPT["sistemas"],     # pol0  renovacion_credencial
    DEPT["compras"],      # pol1  solicitud_insumos
    DEPT["sistemas"],     # pol2  reporte_incidencia_tecnica
    DEPT["rrhh"],         # pol3  permiso_ausencia
    DEPT["compras"],      # pol4  evaluacion_proveedor
]

POL_NAMES = [
    "Renovación de Credencial",
    "Solicitud de Insumos",
    "Reporte de Incidencia Técnica",
    "Permiso de Ausencia",
    "Evaluación de Proveedor",
]

# Formulario definitions per policy, per node type
# Each list = CampoDefinicion dicts
POL_FORMS = {
    # pol0 — renovacion_credencial
    0: {
        "recepcion": [
            {"nombre": "solicitante",       "etiqueta": "Nombre del solicitante",       "tipo": "TEXT",     "requerido": True},
            {"nombre": "descripcion",       "etiqueta": "Motivo de la renovación",      "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "fecha_requerida",   "etiqueta": "Fecha requerida",              "tipo": "DATE",     "requerido": False},
            {"nombre": "doc_cedula",        "etiqueta": "Copia de cédula de identidad", "tipo": "FILE",     "requerido": True},
            {"nombre": "doc_foto_reciente", "etiqueta": "Fotografía reciente (JPG/PNG)","tipo": "FILE",     "requerido": True},
        ],
        "procesamiento": [
            {"nombre": "resultado",         "etiqueta": "Resultado de la gestión",      "tipo": "TEXT",     "requerido": True},
            {"nombre": "doc_credencial",    "etiqueta": "Credencial emitida (PDF)",     "tipo": "FILE",     "requerido": True},
            {"nombre": "observaciones",     "etiqueta": "Observaciones",                "tipo": "TEXTAREA", "requerido": False},
        ],
        "devolucion": [
            {"nombre": "motivo_devolucion", "etiqueta": "Motivo de devolución",         "tipo": "TEXTAREA", "requerido": True},
        ],
    },
    # pol1 — solicitud_insumos
    1: {
        "recepcion": [
            {"nombre": "solicitante",         "etiqueta": "Nombre del solicitante",         "tipo": "TEXT",     "requerido": True},
            {"nombre": "descripcion",         "etiqueta": "Descripción del requerimiento",  "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "fecha_requerida",     "etiqueta": "Fecha de entrega requerida",      "tipo": "DATE",     "requerido": False},
            {"nombre": "doc_formulario_req",  "etiqueta": "Formulario de requisición (PDF)", "tipo": "FILE",     "requerido": True},
            {"nombre": "doc_cotizacion",      "etiqueta": "Cotización de referencia (PDF)",  "tipo": "FILE",     "requerido": False},
        ],
        "procesamiento": [
            {"nombre": "resultado",           "etiqueta": "Resultado de la compra",           "tipo": "TEXT",     "requerido": True},
            {"nombre": "doc_orden_compra",    "etiqueta": "Orden de compra generada (PDF)",    "tipo": "FILE",     "requerido": True},
            {"nombre": "observaciones",       "etiqueta": "Observaciones",                     "tipo": "TEXTAREA", "requerido": False},
        ],
        "devolucion": [
            {"nombre": "motivo_devolucion",   "etiqueta": "Motivo de devolución",              "tipo": "TEXTAREA", "requerido": True},
        ],
    },
    # pol2 — reporte_incidencia_tecnica
    2: {
        "recepcion": [
            {"nombre": "solicitante",         "etiqueta": "Nombre del reportante",              "tipo": "TEXT",     "requerido": True},
            {"nombre": "descripcion",         "etiqueta": "Descripción de la incidencia",       "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "fecha_requerida",     "etiqueta": "Fecha de ocurrencia",                "tipo": "DATE",     "requerido": True},
            {"nombre": "doc_evidencia",       "etiqueta": "Captura de pantalla / evidencia",    "tipo": "FILE",     "requerido": False},
        ],
        "procesamiento": [
            {"nombre": "resultado",           "etiqueta": "Diagnóstico y solución aplicada",    "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "doc_informe_tecnico", "etiqueta": "Informe técnico (PDF)",              "tipo": "FILE",     "requerido": True},
            {"nombre": "observaciones",       "etiqueta": "Observaciones adicionales",          "tipo": "TEXTAREA", "requerido": False},
        ],
        "devolucion": [
            {"nombre": "motivo_devolucion",   "etiqueta": "Motivo de devolución",               "tipo": "TEXTAREA", "requerido": True},
        ],
    },
    # pol3 — permiso_ausencia
    3: {
        "recepcion": [
            {"nombre": "solicitante",         "etiqueta": "Nombre del empleado",                "tipo": "TEXT",     "requerido": True},
            {"nombre": "descripcion",         "etiqueta": "Motivo del permiso",                 "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "fecha_requerida",     "etiqueta": "Fecha de inicio de ausencia",        "tipo": "DATE",     "requerido": True},
            {"nombre": "doc_solicitud_firma", "etiqueta": "Solicitud firmada por el empleado",  "tipo": "FILE",     "requerido": True},
            {"nombre": "doc_certificado",     "etiqueta": "Certificado médico (si aplica)",     "tipo": "FILE",     "requerido": False},
        ],
        "procesamiento": [
            {"nombre": "resultado",           "etiqueta": "Resolución del permiso",             "tipo": "TEXT",     "requerido": True},
            {"nombre": "doc_aprobacion",      "etiqueta": "Documento de aprobación (PDF)",      "tipo": "FILE",     "requerido": True},
            {"nombre": "observaciones",       "etiqueta": "Observaciones",                      "tipo": "TEXTAREA", "requerido": False},
        ],
        "devolucion": [
            {"nombre": "motivo_devolucion",   "etiqueta": "Motivo de devolución",               "tipo": "TEXTAREA", "requerido": True},
        ],
    },
    # pol4 — evaluacion_proveedor
    4: {
        "recepcion": [
            {"nombre": "solicitante",         "etiqueta": "Nombre del solicitante",              "tipo": "TEXT",     "requerido": True},
            {"nombre": "descripcion",         "etiqueta": "Proveedor a evaluar",                 "tipo": "TEXTAREA", "requerido": True},
            {"nombre": "fecha_requerida",     "etiqueta": "Fecha límite de evaluación",          "tipo": "DATE",     "requerido": False},
            {"nombre": "doc_ruc_proveedor",   "etiqueta": "RUC / razón social del proveedor",    "tipo": "FILE",     "requerido": True},
            {"nombre": "doc_propuesta",       "etiqueta": "Propuesta comercial del proveedor",   "tipo": "FILE",     "requerido": True},
        ],
        "procesamiento": [
            {"nombre": "resultado",           "etiqueta": "Resultado de la evaluación",          "tipo": "TEXT",     "requerido": True},
            {"nombre": "doc_informe_eval",    "etiqueta": "Informe de evaluación (PDF)",         "tipo": "FILE",     "requerido": True},
            {"nombre": "observaciones",       "etiqueta": "Observaciones",                       "tipo": "TEXTAREA", "requerido": False},
        ],
        "devolucion": [
            {"nombre": "motivo_devolucion",   "etiqueta": "Motivo de devolución",                "tipo": "TEXTAREA", "requerido": True},
        ],
    },
}

PRIORIDADES = ["LOW", "MEDIUM", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL"]

# Per-policy: 60 tramites
COMPLETED_MAIN = 36   # 60%  — approved path
COMPLETED_ALT  = 12   # 20%  — devolution path
REJECTED_COUNT = 9    # 15%  — hard reject at recepcion
ACTIVE_COUNT   = 3    # 5%   — still open

TRAMITES_PER_POL = COMPLETED_MAIN + COMPLETED_ALT + REJECTED_COUNT + ACTIVE_COUNT  # 60

START_DATE = datetime(2025, 1, 15, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 4, 30, tzinfo=timezone.utc)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _oid(hex24: str) -> dict:
    return {"$oid": hex24}

def _date(dt: datetime) -> dict:
    return {"$date": dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")}

def _make_id(prefix_num: int, seq: int) -> str:
    """prefix_num 1-9 → 24-char hex id, e.g. 1 → '110000000000000000XXXXXX'"""
    return f"{prefix_num}{prefix_num}0000000000000000{seq:06d}"

def _rand_date(lo: datetime, hi: datetime) -> datetime:
    delta = int((hi - lo).total_seconds())
    return lo + timedelta(seconds=random.randint(0, delta))

def _add_hours(dt: datetime, h: float) -> datetime:
    return dt + timedelta(hours=h)

def _add_days(dt: datetime, d: float) -> datetime:
    return dt + timedelta(days=d)

NAMES = ["Ana López", "Carlos Méndez", "María Torres", "José Ramírez",
         "Laura Gómez", "Diego Herrera", "Sofia Castillo", "Miguel Ángel",
         "Camila Ruiz", "Fernando Díaz", "Patricia Vera", "Rodrigo Castro"]

BLOB_BASE = "https://sp1bpmstorage.blob.core.windows.net/documentos"

def _blob_url(filename: str) -> str:
    uid = f"{random.randint(10000,99999)}"
    return f"{BLOB_BASE}/{uid}_{filename}"

def _rand_form_recepcion(pol_idx: int) -> dict:
    descs = [
        "Solicitud urgente de procesamiento.",
        "Documentación adjunta para revisión.",
        "Requiere atención prioritaria.",
        "Caso estándar según normativa vigente.",
        "Seguimiento de solicitud previa.",
    ]
    base = {
        "solicitante": random.choice(NAMES),
        "descripcion": random.choice(descs),
        "fecha_requerida": _rand_date(
            datetime(2025, 2, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 30, tzinfo=timezone.utc)
        ).strftime("%Y-%m-%d"),
    }
    # Add FILE fields per policy
    if pol_idx == 0:  # renovacion_credencial
        base["doc_cedula"]        = _blob_url("cedula.pdf")
        base["doc_foto_reciente"] = _blob_url("foto.jpg")
    elif pol_idx == 1:  # solicitud_insumos
        base["doc_formulario_req"] = _blob_url("requisicion.pdf")
        if random.random() > 0.4:
            base["doc_cotizacion"] = _blob_url("cotizacion.pdf")
    elif pol_idx == 2:  # reporte_incidencia_tecnica
        if random.random() > 0.3:
            base["doc_evidencia"] = _blob_url("captura.png")
    elif pol_idx == 3:  # permiso_ausencia
        base["doc_solicitud_firma"] = _blob_url("solicitud_firmada.pdf")
        if random.random() > 0.5:
            base["doc_certificado"] = _blob_url("certificado_medico.pdf")
    elif pol_idx == 4:  # evaluacion_proveedor
        base["doc_ruc_proveedor"] = _blob_url("ruc_proveedor.pdf")
        base["doc_propuesta"]     = _blob_url("propuesta_comercial.pdf")
    return base

def _rand_form_procesamiento(pol_idx: int) -> dict:
    resultados = {
        0: ["Credencial renovada y entregada al solicitante.", "Credencial emitida — vigencia 2 años.", "Renovación procesada exitosamente."],
        1: ["Orden de compra generada y enviada al proveedor.", "Insumos aprobados y en proceso de adquisición.", "Solicitud de insumos procesada."],
        2: ["Incidencia resuelta — sistema restaurado.", "Fallo corregido — se aplicó parche de seguridad.", "Equipo reemplazado y configurado."],
        3: ["Permiso autorizado por RRHH.", "Ausencia registrada — fechas confirmadas.", "Permiso aprobado sin observaciones."],
        4: ["Proveedor evaluado — calificación APTO.", "Proveedor registrado en lista aprobada.", "Evaluación completada — cumple criterios."],
    }
    doc_names = {
        0: "credencial_emitida.pdf",
        1: "orden_compra.pdf",
        2: "informe_tecnico.pdf",
        3: "aprobacion_permiso.pdf",
        4: "informe_evaluacion.pdf",
    }
    file_field = {0: "doc_credencial", 1: "doc_orden_compra", 2: "doc_informe_tecnico",
                  3: "doc_aprobacion", 4: "doc_informe_eval"}
    return {
        "resultado": random.choice(resultados[pol_idx]),
        file_field[pol_idx]: _blob_url(doc_names[pol_idx]),
        "observaciones": random.choice(["Sin observaciones adicionales.", "Proceso completado en tiempo estándar.", ""]),
    }

def _rand_form_devolucion() -> dict:
    motivos = [
        "Documentación incompleta — falta copia de cédula.",
        "La solicitud no cumple los requisitos mínimos.",
        "El solicitante debe completar el formulario F-03.",
        "Período de solicitud no aplica según normativa.",
        "Falta firma del supervisor inmediato.",
        "El archivo adjunto está ilegible o dañado.",
        "Los datos del formulario no coinciden con los documentos adjuntos.",
    ]
    return {"motivo_devolucion": random.choice(motivos)}

# ── NODOS ──────────────────────────────────────────────────────────────────────

def gen_nodos() -> list:
    nodos = []
    seq = 1
    for pi in range(5):
        ver_id = VERSION_IDS[pi]
        proc_dept = POL_PROC_DEPT[pi]
        label = POL_NAMES[pi]
        created = _date(datetime(2025, 1, 1, tzinfo=timezone.utc))

        nodos += [
            # START
            {
                "_id": _oid(_make_id(1, seq)),
                "versionPoliticaId": ver_id,
                "nodoId": "inicio",
                "calleId": None,
                "tipoNodo": "START",
                "etiqueta": "Inicio",
                "salidas": [{"nodoDestino": "recepcion", "rama": True, "etiqueta": ""}],
                "formulario": [],
                "posicionCanvas": {"x": 80, "y": 220},
                "instruccionAvance": None,
                "instruccionRechazo": None,
                "creadoEn": created,
            },
            # ACTIVITY recepcion
            {
                "_id": _oid(_make_id(1, seq + 1)),
                "versionPoliticaId": ver_id,
                "nodoId": "recepcion",
                "calleId": "recepcion",
                "tipoNodo": "ACTIVITY",
                "etiqueta": f"Recepción — {label}",
                "departamentoId": DEPT["recepcion"],
                "salidas": [{"nodoDestino": "revision", "rama": True, "etiqueta": ""}],
                "formulario": POL_FORMS[pi]["recepcion"],
                "instruccionAvance": "Verificar documentación y registrar la solicitud. Adjuntar los archivos requeridos.",
                "instruccionRechazo": "Rechazar si la documentación está incompleta, ilegible o fuera de plazo.",
                "posicionCanvas": {"x": 280, "y": 220},
                "creadoEn": created,
            },
            # DECISION revision
            {
                "_id": _oid(_make_id(1, seq + 2)),
                "versionPoliticaId": ver_id,
                "nodoId": "revision",
                "calleId": None,
                "tipoNodo": "DECISION",
                "etiqueta": "Revisión",
                "salidas": [
                    {"nodoDestino": "procesamiento", "rama": False, "etiqueta": "Aprobado"},
                    {"nodoDestino": "devolucion",    "rama": True,  "etiqueta": "Devolver"},
                ],
                "formulario": [],
                "posicionCanvas": {"x": 480, "y": 220},
                "instruccionAvance": None,
                "instruccionRechazo": None,
                "creadoEn": created,
            },
            # ACTIVITY procesamiento (approved)
            {
                "_id": _oid(_make_id(1, seq + 3)),
                "versionPoliticaId": ver_id,
                "nodoId": "procesamiento",
                "calleId": "procesamiento",
                "tipoNodo": "ACTIVITY",
                "etiqueta": f"Procesamiento — {label}",
                "departamentoId": proc_dept,
                "salidas": [{"nodoDestino": "fin", "rama": True, "etiqueta": ""}],
                "formulario": POL_FORMS[pi]["procesamiento"],
                "instruccionAvance": "Procesar la solicitud aprobada. Adjuntar el documento de resolución.",
                "instruccionRechazo": "Devolver si no es posible procesar.",
                "posicionCanvas": {"x": 680, "y": 100},
                "creadoEn": created,
            },
            # ACTIVITY devolucion (alt path)
            {
                "_id": _oid(_make_id(1, seq + 4)),
                "versionPoliticaId": ver_id,
                "nodoId": "devolucion",
                "calleId": "devolucion",
                "tipoNodo": "ACTIVITY",
                "etiqueta": f"Devolución — {label}",
                "departamentoId": proc_dept,
                "salidas": [{"nodoDestino": "fin", "rama": True, "etiqueta": ""}],
                "formulario": POL_FORMS[pi]["devolucion"],
                "instruccionAvance": "Documentar el motivo de devolución y notificar al solicitante.",
                "instruccionRechazo": None,
                "posicionCanvas": {"x": 680, "y": 340},
                "creadoEn": created,
            },
            # END
            {
                "_id": _oid(_make_id(1, seq + 5)),
                "versionPoliticaId": ver_id,
                "nodoId": "fin",
                "calleId": None,
                "tipoNodo": "END",
                "etiqueta": "Fin",
                "salidas": [],
                "formulario": [],
                "posicionCanvas": {"x": 880, "y": 220},
                "instruccionAvance": None,
                "instruccionRechazo": None,
                "creadoEn": created,
            },
        ]
        seq += 6

    return nodos


# ── TRAMITES + TASKS + EVENTS ──────────────────────────────────────────────────

def gen_all():
    tramites      = []
    tasks         = []
    events        = []
    ticket_seq    = 1
    tramite_seq   = 1
    task_seq      = 1
    event_seq     = 1

    def new_tramite_id(): nonlocal tramite_seq; v = tramite_seq; tramite_seq += 1; return _make_id(2, v)
    def new_task_id():    nonlocal task_seq;    v = task_seq;    task_seq    += 1; return _make_id(3, v)
    def new_event_id():   nonlocal event_seq;   v = event_seq;   event_seq   += 1; return _make_id(4, v)
    def new_ticket():     nonlocal ticket_seq;  v = ticket_seq;  ticket_seq  += 1; return f"TRM-2026-{v:04d}"

    for pi in range(5):
        pol_id  = POLITICA_IDS[pi]
        ver_id  = VERSION_IDS[pi]
        proc_dept = POL_PROC_DEPT[pi]

        # Build list of (type, main_path) tuples
        cases = (
            [("COMPLETED_MAIN", True)]  * COMPLETED_MAIN +
            [("COMPLETED_ALT",  False)] * COMPLETED_ALT  +
            [("REJECTED",       None)]  * REJECTED_COUNT +
            [("ACTIVE",         None)]  * ACTIVE_COUNT
        )
        random.shuffle(cases)

        for case_type, main_path in cases:
            t_id     = new_tramite_id()
            ticket   = new_ticket()
            actor    = random.choice(ACTORS)
            prioridad = random.choice(PRIORIDADES)
            started  = _rand_date(START_DATE, END_DATE)

            # ── COMPLETED main path ────────────────────────────────────────────
            if case_type == "COMPLETED_MAIN":
                task1_id = new_task_id()
                task2_id = new_task_id()

                t1_created = _add_hours(started, random.uniform(0.1, 2))
                t1_comp    = _add_days(t1_created, random.uniform(0.5, 3))
                t2_created = _add_hours(t1_comp, random.uniform(0.5, 4))
                t2_comp    = _add_days(t2_created, random.uniform(1, 5))
                completed_at = _add_hours(t2_comp, random.uniform(0.1, 1))

                tramites.append({
                    "_id": _oid(t_id),
                    "politicaId": pol_id,
                    "versionPoliticaId": ver_id,
                    "status": "COMPLETED",
                    "currentNodeIds": ["fin"],
                    "prioridad": prioridad,
                    "initiatedBy": actor,
                    "ticketNumber": ticket,
                    "startedAt": _date(started),
                    "completedAt": _date(completed_at),
                    "fcmToken": None,
                })

                # Task 1 — recepcion
                tasks.append({
                    "_id": _oid(task1_id),
                    "tramiteId": t_id,
                    "nodeId": "recepcion",
                    "calleId": "recepcion",
                    "departamentoId": DEPT["recepcion"],
                    "assignedTo": actor,
                    "status": "COMPLETED",
                    "formData": _rand_form_recepcion(pi),
                    "branchSelected": None,
                    "createdAt": _date(t1_created),
                    "updatedAt": _date(t1_comp),
                    "completedAt": _date(t1_comp),
                })

                # Task 2 — procesamiento
                tasks.append({
                    "_id": _oid(task2_id),
                    "tramiteId": t_id,
                    "nodeId": "procesamiento",
                    "calleId": "procesamiento",
                    "departamentoId": proc_dept,
                    "assignedTo": actor,
                    "status": "COMPLETED",
                    "formData": _rand_form_procesamiento(pi),
                    "branchSelected": False,
                    "createdAt": _date(t2_created),
                    "updatedAt": _date(t2_comp),
                    "completedAt": _date(t2_comp),
                })

                # Events
                for e in [
                    {"tipo": "STARTED",        "nodeId": None,             "taskId": None,     "actorId": actor,  "ts": started,     "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "inicio",         "taskId": None,     "actorId": None,   "ts": started,     "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "recepcion",      "taskId": None,     "actorId": None,   "ts": t1_created,  "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "TASK_COMPLETED", "nodeId": "recepcion",      "taskId": task1_id, "actorId": actor,  "ts": t1_comp,     "branchTaken": None, "comentario": None, "formData": _rand_form_recepcion(pi)},
                    {"tipo": "NODE_ENTERED",   "nodeId": "revision",       "taskId": None,     "actorId": None,   "ts": t1_comp,     "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "DECISION_TAKEN", "nodeId": "revision",       "taskId": None,     "actorId": actor,  "ts": _add_hours(t1_comp, 0.1), "branchTaken": False, "comentario": None, "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "procesamiento",  "taskId": None,     "actorId": None,   "ts": t2_created,  "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "TASK_COMPLETED", "nodeId": "procesamiento",  "taskId": task2_id, "actorId": actor,  "ts": t2_comp,     "branchTaken": None, "comentario": None, "formData": _rand_form_procesamiento(pi)},
                    {"tipo": "NODE_ENTERED",   "nodeId": "fin",            "taskId": None,     "actorId": None,   "ts": completed_at,"branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "COMPLETED",      "nodeId": None,             "taskId": None,     "actorId": actor,  "ts": completed_at,"branchTaken": None, "comentario": None, "formData": None},
                ]:
                    events.append({
                        "_id": _oid(new_event_id()),
                        "tramiteId": t_id,
                        "tipo": e["tipo"],
                        "nodeId": e["nodeId"],
                        "calleId": None,
                        "taskId": e["taskId"],
                        "actorId": e["actorId"],
                        "formData": e["formData"],
                        "branchTaken": e["branchTaken"],
                        "comentario": e["comentario"],
                        "timestamp": _date(e["ts"]),
                    })

            # ── COMPLETED alt path (devolucion) ────────────────────────────────
            elif case_type == "COMPLETED_ALT":
                task1_id = new_task_id()
                task2_id = new_task_id()

                t1_created = _add_hours(started, random.uniform(0.1, 2))
                t1_comp    = _add_days(t1_created, random.uniform(0.5, 2))
                t2_created = _add_hours(t1_comp, random.uniform(0.5, 4))
                t2_comp    = _add_days(t2_created, random.uniform(1, 4))
                completed_at = _add_hours(t2_comp, random.uniform(0.1, 1))

                tramites.append({
                    "_id": _oid(t_id),
                    "politicaId": pol_id,
                    "versionPoliticaId": ver_id,
                    "status": "COMPLETED",
                    "currentNodeIds": ["fin"],
                    "prioridad": prioridad,
                    "initiatedBy": actor,
                    "ticketNumber": ticket,
                    "startedAt": _date(started),
                    "completedAt": _date(completed_at),
                    "fcmToken": None,
                })

                # Task 1 — recepcion
                tasks.append({
                    "_id": _oid(task1_id),
                    "tramiteId": t_id,
                    "nodeId": "recepcion",
                    "calleId": "recepcion",
                    "departamentoId": DEPT["recepcion"],
                    "assignedTo": actor,
                    "status": "COMPLETED",
                    "formData": _rand_form_recepcion(pi),
                    "branchSelected": None,
                    "createdAt": _date(t1_created),
                    "updatedAt": _date(t1_comp),
                    "completedAt": _date(t1_comp),
                })

                # Task 2 — devolucion
                tasks.append({
                    "_id": _oid(task2_id),
                    "tramiteId": t_id,
                    "nodeId": "devolucion",
                    "calleId": "devolucion",
                    "departamentoId": proc_dept,
                    "assignedTo": actor,
                    "status": "COMPLETED",
                    "formData": _rand_form_devolucion(),
                    "branchSelected": True,
                    "createdAt": _date(t2_created),
                    "updatedAt": _date(t2_comp),
                    "completedAt": _date(t2_comp),
                })

                for e in [
                    {"tipo": "STARTED",        "nodeId": None,          "taskId": None,     "actorId": actor,  "ts": started,    "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "inicio",      "taskId": None,     "actorId": None,   "ts": started,    "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "recepcion",   "taskId": None,     "actorId": None,   "ts": t1_created, "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "TASK_COMPLETED", "nodeId": "recepcion",   "taskId": task1_id, "actorId": actor,  "ts": t1_comp,    "branchTaken": None, "comentario": None, "formData": _rand_form_recepcion(pi)},
                    {"tipo": "NODE_ENTERED",   "nodeId": "revision",    "taskId": None,     "actorId": None,   "ts": t1_comp,    "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "DECISION_TAKEN", "nodeId": "revision",    "taskId": None,     "actorId": actor,  "ts": _add_hours(t1_comp, 0.1), "branchTaken": True, "comentario": "No cumple requisitos.", "formData": None},
                    {"tipo": "NODE_ENTERED",   "nodeId": "devolucion",  "taskId": None,     "actorId": None,   "ts": t2_created, "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "TASK_COMPLETED", "nodeId": "devolucion",  "taskId": task2_id, "actorId": actor,  "ts": t2_comp,    "branchTaken": None, "comentario": None, "formData": _rand_form_devolucion()},
                    {"tipo": "NODE_ENTERED",   "nodeId": "fin",         "taskId": None,     "actorId": None,   "ts": completed_at, "branchTaken": None, "comentario": None, "formData": None},
                    {"tipo": "COMPLETED",      "nodeId": None,          "taskId": None,     "actorId": actor,  "ts": completed_at, "branchTaken": None, "comentario": None, "formData": None},
                ]:
                    events.append({
                        "_id": _oid(new_event_id()),
                        "tramiteId": t_id,
                        "tipo": e["tipo"],
                        "nodeId": e["nodeId"],
                        "calleId": None,
                        "taskId": e["taskId"],
                        "actorId": e["actorId"],
                        "formData": e["formData"],
                        "branchTaken": e["branchTaken"],
                        "comentario": e["comentario"],
                        "timestamp": _date(e["ts"]),
                    })

            # ── REJECTED ───────────────────────────────────────────────────────
            elif case_type == "REJECTED":
                task1_id = new_task_id()

                t1_created = _add_hours(started, random.uniform(0.1, 2))
                t1_rej     = _add_days(t1_created, random.uniform(0.2, 1.5))
                cancelled_at = _add_hours(t1_rej, random.uniform(0.05, 0.5))

                tramites.append({
                    "_id": _oid(t_id),
                    "politicaId": pol_id,
                    "versionPoliticaId": ver_id,
                    "status": "REJECTED",
                    "currentNodeIds": [],
                    "prioridad": prioridad,
                    "initiatedBy": actor,
                    "ticketNumber": ticket,
                    "startedAt": _date(started),
                    "completedAt": _date(cancelled_at),
                    "fcmToken": None,
                })

                tasks.append({
                    "_id": _oid(task1_id),
                    "tramiteId": t_id,
                    "nodeId": "recepcion",
                    "calleId": "recepcion",
                    "departamentoId": DEPT["recepcion"],
                    "assignedTo": actor,
                    "status": "REJECTED",
                    "formData": _rand_form_recepcion(pi),
                    "branchSelected": None,
                    "createdAt": _date(t1_created),
                    "updatedAt": _date(t1_rej),
                    "completedAt": None,
                })

                motivos = [
                    "El solicitante no presenta los documentos exigidos.",
                    "Solicitud duplicada — ya existe un trámite activo.",
                    "El solicitante no pertenece a la unidad organizacional correcta.",
                    "Período de solicitud fuera de los plazos establecidos.",
                    "Formulario presentado con datos incorrectos.",
                ]
                for e in [
                    {"tipo": "STARTED",       "nodeId": None,        "taskId": None,     "actorId": actor,  "ts": started,    "branchTaken": None, "comentario": None},
                    {"tipo": "NODE_ENTERED",  "nodeId": "inicio",    "taskId": None,     "actorId": None,   "ts": started,    "branchTaken": None, "comentario": None},
                    {"tipo": "NODE_ENTERED",  "nodeId": "recepcion", "taskId": None,     "actorId": None,   "ts": t1_created, "branchTaken": None, "comentario": None},
                    {"tipo": "TASK_REJECTED", "nodeId": "recepcion", "taskId": task1_id, "actorId": actor,  "ts": t1_rej,     "branchTaken": None, "comentario": random.choice(motivos)},
                    {"tipo": "CANCELLED",     "nodeId": None,        "taskId": None,     "actorId": actor,  "ts": cancelled_at, "branchTaken": None, "comentario": None},
                ]:
                    events.append({
                        "_id": _oid(new_event_id()),
                        "tramiteId": t_id,
                        "tipo": e["tipo"],
                        "nodeId": e["nodeId"],
                        "calleId": None,
                        "taskId": e["taskId"],
                        "actorId": e["actorId"],
                        "formData": None,
                        "branchTaken": e["branchTaken"],
                        "comentario": e.get("comentario"),
                        "timestamp": _date(e["ts"]),
                    })

            # ── ACTIVE ─────────────────────────────────────────────────────────
            elif case_type == "ACTIVE":
                task1_id = new_task_id()
                t1_created = _add_hours(started, random.uniform(0.1, 2))
                # Active tasks: use recent dates so they feel "current"
                recent_start = _rand_date(datetime(2026, 3, 1, tzinfo=timezone.utc),
                                          datetime(2026, 5, 20, tzinfo=timezone.utc))
                t1_created = _add_hours(recent_start, random.uniform(0.5, 8))
                task_status = random.choice(["PENDING", "IN_PROGRESS"])

                tramites.append({
                    "_id": _oid(t_id),
                    "politicaId": pol_id,
                    "versionPoliticaId": ver_id,
                    "status": "ACTIVE",
                    "currentNodeIds": ["recepcion"],
                    "prioridad": prioridad,
                    "initiatedBy": actor,
                    "ticketNumber": ticket,
                    "startedAt": _date(recent_start),
                    "completedAt": None,
                    "fcmToken": None,
                })

                tasks.append({
                    "_id": _oid(task1_id),
                    "tramiteId": t_id,
                    "nodeId": "recepcion",
                    "calleId": "recepcion",
                    "departamentoId": DEPT["recepcion"],
                    "assignedTo": actor if task_status == "IN_PROGRESS" else None,
                    "status": task_status,
                    "formData": None,
                    "branchSelected": None,
                    "createdAt": _date(t1_created),
                    "updatedAt": _date(t1_created),
                    "completedAt": None,
                })

                for e in [
                    {"tipo": "STARTED",       "nodeId": None,        "taskId": None, "actorId": actor, "ts": recent_start},
                    {"tipo": "NODE_ENTERED",  "nodeId": "inicio",    "taskId": None, "actorId": None,  "ts": recent_start},
                    {"tipo": "NODE_ENTERED",  "nodeId": "recepcion", "taskId": None, "actorId": None,  "ts": t1_created},
                ]:
                    events.append({
                        "_id": _oid(new_event_id()),
                        "tramiteId": t_id,
                        "tipo": e["tipo"],
                        "nodeId": e["nodeId"],
                        "calleId": None,
                        "taskId": e["taskId"],
                        "actorId": e["actorId"],
                        "formData": None,
                        "branchTaken": None,
                        "comentario": None,
                        "timestamp": _date(e["ts"]),
                    })

    return tramites, tasks, events


# ── COUNTERS ───────────────────────────────────────────────────────────────────

def gen_counters(total_tramites: int) -> list:
    return [{"_id": "tramite_counter", "seq": total_tramites}]


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    out = Path(__file__).parent

    print("Generating nodos...")
    nodos = gen_nodos()
    print(f"  {len(nodos)} nodos")

    print("Generating tramites / tasks / events...")
    tramites, tasks, events = gen_all()
    print(f"  {len(tramites)} tramites")
    print(f"  {len(tasks)} tasks")
    print(f"  {len(events)} tramite_events")

    counters = gen_counters(len(tramites))

    for fname, data in [
        ("nodos.json",          nodos),
        ("tramites.json",       tramites),
        ("tasks.json",          tasks),
        ("tramite_events.json", events),
        ("counters.json",       counters),
    ]:
        path = out / fname
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  → {path}  ({len(data)} docs)")

    print("\nDone! Import order:")
    print("  1. db.nodos.insertMany( <nodos.json> )")
    print("  2. db.tramites.insertMany( <tramites.json> )")
    print("  3. db.tasks.insertMany( <tasks.json> )")
    print("  4. db.tramite_events.insertMany( <tramite_events.json> )")
    print("  5. db.counters.insertMany( <counters.json> )  — or updateOne if already exists")


if __name__ == "__main__":
    main()
