# sp1-backend-py — Estructura del proyecto

Backend FastAPI que reemplaza al Spring Boot caído.
Conecta a la misma base de datos MongoDB Atlas del Ciclo 1 sin migrar datos.

---

## Árbol de carpetas

```
sp1-backend-py/
│
├── main.py                          ← ⚙️  Punto de entrada: FastAPI app, CORS, routers, lifespan
├── config.py                        ← ⚙️  Settings (pydantic-settings): lee .env
├── database.py                      ← ⚙️  Conexión MongoDB Atlas + init_beanie()
├── requirements.txt                 ← 📦 Dependencias pip
├── .env.example                     ← 🔑 Variables de entorno (copiar a .env)
├── Dockerfile                       ← 🐳 Imagen para docker-compose (PENDIENTE)
│
├── models/                          ← 🗄️  Documentos Beanie (mapean colecciones Atlas)
│   ├── user.py                      │     → colección: usuarios
│   ├── departamento.py              │     → colección: departamentos
│   ├── politica.py                  │     → colección: politicas
│   ├── version_politica.py          │     → colección: versiones_politica  (embebe Calle[])
│   ├── nodo.py                      │     → colección: nodos               (embebe Destinos[], CampoDefinicion[])
│   ├── tramite.py                   │     → colección: tramites
│   ├── task.py                      │     → colección: tasks
│   └── tramite_event.py             │     → colección: tramite_events      (event sourcing, inmutable)
│
├── schemas/                         ← 📋 Pydantic request/response (NO son documentos Beanie)
│   ├── auth.py                      │     LoginRequest, LoginResponse
│   ├── user.py                      │     CreateUserRequest, UpdateUserRequest, UserResponse
│   ├── departamento.py              │     CreateDepartamentoRequest, DepartamentoResponse
│   ├── politica.py                  │     CreatePoliticaRequest, PoliticaResponse, VersionResponse, DiagramaResponse
│   ├── nodo.py                      │     CreateNodoRequest, NodoResponse, CalleRequest, ValidacionResultado, InstruccionRequest
│   ├── tramite.py                   │     CreateTramiteRequest, TramiteResponse, TramiteEventResponse, FcmTokenRequest
│   └── task.py                      │     TaskResponse, CompletarTareaRequest, RechazarTareaRequest, DelegarTareaRequest
│
├── routers/                         ← 🌐 Endpoints HTTP (APIRouter por módulo)
│   ├── auth.py                      │     POST /api/auth/login
│   ├── users.py                     │     CRUD /api/users
│   ├── departamentos.py             │     CRUD /api/departamentos
│   ├── politicas.py                 │     CRUD /api/policies  +  GET /api/policies/public
│   ├── versiones.py                 │     /api/policies/{id}/versions  +  /lanes  +  /publish  +  /validate  +  /ai-generate
│   ├── nodos.py                     │     /api/versions/{vid}/nodes  +  /connections
│   ├── tramites.py                  │     CRUD /api/tramites  +  /ticket/{n}  +  /history  +  /tasks
│   ├── tasks.py                     │     ⚠️  PENDIENTE — /api/tasks/my-tasks, /take, /complete, /reject, /delegate
│   ├── metricas.py                  │     ⚠️  PENDIENTE — GET /api/metrics/bottlenecks, /performance
│   └── ws.py                        │     ⚠️  PENDIENTE — WebSocket /ws/canvas/{vid}, /ws/tramites/{id}, /ws/tareas/{uid}
│
├── services/                        ← 🧠 Lógica de negocio
│   ├── auth_service.py              │     login() → valida credenciales, genera JWT
│   ├── ticket_service.py            │     generate_ticket() → TRM-YYYY-XXXX secuencial
│   ├── ai_service.py                │     generate_diagram() → proxy a sp1-ai /generate
│   ├── metricas_service.py          │     get_bottlenecks(), get_performance()
│   │
│   ├── workflow/                    ← 🔄 Motor de workflow (Strategy Pattern completo)
│   │   ├── workflow_context.py      │     WorkflowContext — datos de ejecución (tramite, nodo, actor, branch…)
│   │   ├── workflow_engine.py       │     WorkflowEngine — orquesta el flujo entre nodos
│   │   └── handlers/                │
│   │       ├── base.py              │       NodeHandler (ABC) — interfaz del Strategy
│   │       ├── start_handler.py     │       START  → registra NODE_ENTERED, el motor avanza
│   │       ├── activity_handler.py  │       ACTIVITY → crea Task, DETIENE el flujo
│   │       ├── decision_handler.py  │       DECISION → registra DECISION_TAKEN (el motor filtra rama T/F)
│   │       ├── merge_handler.py     │       MERGE → pasa el primer flujo que llega (OR-join)
│   │       ├── fork_handler.py      │       FORK → registra FORK_SPLIT (el motor lanza paralelo)
│   │       ├── join_handler.py      │       JOIN → contador atómico MongoDB, avanza solo cuando llegan TODAS las ramas
│   │       └── end_handler.py       │       END  → marca trámite COMPLETED, vacía currentNodeIds
│   │
│   └── canvas/                      ← 🎨 Canvas colaborativo (presencia en tiempo real)
│       └── canvas_session_manager.py│     CanvasSessionManager — quién está editando, colores de cursor
│
└── core/                            ← 🔒 Infraestructura transversal
    ├── security.py                  │     verify_password, hash_password, create_access_token, get_current_user, require_roles
    ├── exceptions.py                │     NotFoundException, BusinessException, UserAlreadyExistsException, PoliticaInmutableException, AiServiceException
    └── websocket_manager.py         │     WebSocketManager — pub/sub nativo (topics: canvas/{id}, tramites/{id}, tareas/{uid}, alertas)
```

---

## Archivos PENDIENTES de crear

| Archivo | Qué hace |
|---------|----------|
| `main.py` | App FastAPI, registra todos los routers, lifespan con `init_db()`, CORS |
| `routers/tasks.py` | Bandeja de tareas: `my-tasks`, `take`, `complete`, `reject`, `delegate` + llama al motor |
| `routers/metricas.py` | GET `/api/metrics/bottlenecks` y `/performance` |
| `routers/ws.py` | Endpoints WebSocket nativos: canvas colaborativo + estado trámite + notificaciones |
| `Dockerfile` | Imagen Python para `docker-compose up` |

---

## Flujo de datos clave

### Login
```
POST /api/auth/login
  → auth_service.login()
  → User.find_one(email)  [colección: usuarios]
  → passlib.verify_password(plain, BCrypt_hash_de_Spring)
  → create_access_token(email, rol)  [mismo formato JWT que Spring]
  → { token, expiresIn, userId, nombre, rol }
```

### Iniciar trámite + motor de workflow
```
POST /api/tramites
  → Tramite.insert()  [colección: tramites]
  → generate_ticket() → TRM-2026-XXXX
  → workflow_engine.start_tramite()
      → Nodo.find_one(tipo=START)
      → StartNodeHandler.handle()  → TramiteEvent(NODE_ENTERED)
      → avanzar a sucesores del START
      → ActivityNodeHandler.handle()  → Task.insert() + DETENER
  → broadcast ws_manager topic: tramites/{id}
```

### Completar tarea (PENDIENTE en tasks.py)
```
POST /api/tasks/{id}/complete
  → Task.update(status=COMPLETED, formData, branchSelected)
  → TramiteEvent(TASK_COMPLETED)
  → workflow_engine.advance(tramite, nodo, actor, branchSelected)
      → handler del nodo (DECISION/MERGE/FORK/JOIN/END)
      → avanzar a sucesores
  → broadcast ws_manager topic: tramites/{tramiteId}
                                 tareas/{userId}
```

### Canvas colaborativo (PENDIENTE en ws.py)
```
WebSocket /ws/canvas/{versionId}?token=JWT
  → validar JWT
  → canvas_session_manager.join(versionId, userId, nombre)
  → broadcast presencia a todos en el canvas
  → recibir eventos: NODE_MOVED, NODE_CREATED, CONNECTION_CREATED, etc.
  → ws_manager.broadcast(f"canvas/{versionId}", evento)
  → al desconectar: canvas_session_manager.leave()
```

---

## Colecciones MongoDB Atlas (NO modificar nombres)

| Colección | Modelo Beanie |
|-----------|--------------|
| `usuarios` | `User` |
| `departamentos` | `Departamento` |
| `politicas` | `Politica` |
| `versiones_politica` | `VersionPolitica` |
| `nodos` | `Nodo` |
| `tramites` | `Tramite` |
| `tasks` | `Task` |
| `tramite_events` | `TramiteEvent` |

---

## Variables de entorno (.env)

```env
MONGODB_URI=mongodb+srv://usuario:password@cluster.mongodb.net/swp1_db
JWT_SECRET=bpm-super-secret-key-2026-debe-tener-256-bits-minimo
JWT_EXPIRATION_HOURS=8
AI_SERVICE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:4200,http://localhost:3000
```

---

## Correr localmente

```bash
cd sp1-backend-py
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar con Atlas URI y JWT_SECRET
uvicorn main:app --reload --port 8080
```

Swagger UI → http://localhost:8080/docs

---

## Mejoras arquitectónicas a implementar

Estas piezas **no están en el backend Java original** pero deben añadirse al nuevo backend Python para que escale bien al Ciclo 2 (MIRA, agente IA, reportes dinámicos) sin tocar el motor central.

---

### 1. `core/event_bus.py` — Pub/sub async in-process

**Qué es:** ~30 líneas, cero dependencias externas. Un `EventBus` que permite emitir un evento (`emit`) y que múltiples listeners asíncronos reaccionen de forma desacoplada.

**Por qué:** Actualmente el `WorkflowEngine` hace todo en línea: persiste en `tramite_events`, hace broadcast WS y crearía la notificación al funcionario, todo en el mismo bloque. Eso es difícil de extender. Con un EventBus el engine solo emite `node_processed` o `task_created`; cada listener reacciona por su cuenta.

**Clave para Ciclo 2:** cuando lleguen el motor inteligente MIRA, los reportes dinámicos y el agente IA, cada uno será un listener nuevo (`on("task_created", mira_listener)`). El engine no se toca.

```python
# Uso esperado
await event_bus.emit("task_created", {"task_id": ..., "tramite_id": ...})
await event_bus.emit("node_processed", {"node_id": ..., "tipo": "ACTIVITY"})
```

**Eventos a emitir desde el workflow engine:**

| Evento | Cuándo | Payload mínimo |
|---|---|---|
| `node_processed` | Al ejecutar cualquier handler | `tramite_id`, `node_id`, `tipo_nodo` |
| `task_created` | `ActivityNodeHandler` crea una Task | `task_id`, `tramite_id`, `node_id`, `departamento_id` |
| `tramite_completed` | `EndNodeHandler` completa el trámite | `tramite_id`, `ticket_number` |
| `tramite_advanced` | Después de cada avance del motor | `tramite_id`, `current_node_ids` |

---

### 2. `core/http_client.py` — `httpx.AsyncClient` singleton con connection pooling

**Qué es:** Un cliente HTTP compartido con `limits` configurados, creado una sola vez en el lifespan de la app y cerrado limpiamente al apagar.

**Por qué:** `ai_service.py` actualmente abre y cierra un `AsyncClient` por cada llamada (`async with httpx.AsyncClient()`). Con el Ciclo 2 habrá más servicios externos (MIRA, agente IA, reportes). Abrir un cliente nuevo por request desperdicia conexiones TCP y agrega latencia.

```python
# En main.py lifespan:
async with lifespan(app):
    await http_client.start()   # crea el pool
    yield
    await http_client.aclose()  # cierra ordenadamente

# En ai_service.py:
from core.http_client import http_client
response = await http_client.post(url, json=payload)
```

---

### 3. `services/workflow/handler_result.py` — `HandlerResult` tipado

**Qué es:** Un dataclass que cada handler retorna en lugar de `void`. Hace explícito si el flujo avanza, se detiene o lanza paralelo.

**Por qué:** Ahora el engine infiere el comportamiento del handler mirando el `TipoNodo` después del hecho. Con `HandlerResult` cada handler declara su intención de forma clara, y el engine no necesita conocer los tipos de nodo para decidir qué hacer.

```python
@dataclass
class HandlerResult:
    stop: bool = False             # True → flujo detenido (ACTIVITY, JOIN incompleto)
    next_node_ids: list[str] = field(default_factory=list)  # vacío → engine calcula por salidas
    event_type: str = ""           # tipo a emitir en el EventBus
    extra: dict = field(default_factory=dict)  # payload libre para el EventBus

# Ejemplo en ActivityNodeHandler:
return HandlerResult(stop=True, event_type="task_created", extra={"task_id": str(task.id)})

# Ejemplo en ForkHandler:
return HandlerResult(stop=False, next_node_ids=[s.nodoDestino for s in ctx.nodo.salidas])
```

**Beneficio adicional:** facilita el testing — cada handler se puede probar en aislamiento verificando el `HandlerResult` sin necesitar la base de datos.

---

### 4. `listeners/` — carpeta nueva con suscriptores del EventBus

**Qué es:** Carpeta separada de `services/` donde vive la lógica reactiva. Cada archivo se suscribe a uno o más eventos del `EventBus`.

**Estructura:**

```
listeners/
├── __init__.py               ← registra todos los listeners (import basta para activarlos)
├── event_persistence.py      ← on("node_processed") → inserta TramiteEvent en MongoDB
├── ws_broadcaster.py         ← on("tramite_advanced") → ws_manager.broadcast("tramites/{id}", ...)
└── task_notifier.py          ← on("task_created") → ws_manager.broadcast("tareas/{userId}", ...)
```

**`listeners/__init__.py`** (una sola línea por listener):
```python
from . import event_persistence, ws_broadcaster, task_notifier
```

**Clave para Ciclo 2** — añadir soporte para MIRA sin tocar nada existente:
```python
# listeners/mira_listener.py  (nuevo en Ciclo 2)
from core.event_bus import event_bus

@event_bus.on("task_created")
async def notify_mira(payload):
    await mira_service.analyze_risk(payload["tramite_id"])
```

Y en `__init__.py` agregar una línea: `from . import mira_listener`.

---

### 5. Split de `routers/ws.py` en tres archivos

**Por qué un solo `ws.py` no escala:** el canvas colaborativo, el seguimiento de trámites y las notificaciones de tareas tienen lógica completamente distinta. El canvas tiene presencia (quién está editando), autenticación requerida y rebroadcast de eventos de nodo. El de trámites es solo lectura para Flutter (sin auth). El de tareas es push a un usuario específico. En Ciclo 2 cada uno va a crecer con más eventos.

**Split propuesto:**

```
routers/
├── ws_canvas.py    ← WebSocket /ws/canvas/{versionId}?token=JWT
│                      · Valida JWT obligatorio
│                      · canvas_session_manager.join() al conectar, .leave() al desconectar
│                      · Broadcast presencia (usuarios conectados con color de cursor)
│                      · Rebroadcast de eventos: NODE_MOVED, NODE_CREATED, CONNECTION_CREATED, etc.
│                      · Crece con: modo "solo lectura" para supervisores, historial de cambios
│
├── ws_tramites.py  ← WebSocket /ws/tramites/{tramiteId}
│                      · Sin auth (público — Flutter)
│                      · Solo lectura: recibe broadcasts del workflow engine
│                      · Crece con: heartbeat/ping para saber si el trámite sigue activo
│
└── ws_tareas.py    ← WebSocket /ws/tareas/{userId}?token=JWT
                       · Valida JWT, verifica que userId == current_user.id
                       · Recibe notificaciones push: nuevas tareas asignadas
                       · Crece con: alertas del sistema (/topic/alertas del supervisor)
```

**En `main.py`** — registrar los tres:
```python
app.include_router(ws_canvas.router)
app.include_router(ws_tramites.router)
app.include_router(ws_tareas.router)
```

---

### Árbol final con las mejoras incorporadas

```
sp1-backend-py/
│
├── core/
│   ├── security.py
│   ├── exceptions.py
│   ├── websocket_manager.py
│   ├── event_bus.py          ← NUEVO: pub/sub async in-process
│   └── http_client.py        ← NUEVO: httpx singleton con connection pooling
│
├── listeners/                ← NUEVA carpeta
│   ├── __init__.py           ← registra todos los listeners
│   ├── event_persistence.py  ← persiste TramiteEvent en MongoDB
│   ├── ws_broadcaster.py     ← broadcast estado trámite por WS
│   └── task_notifier.py      ← notifica al funcionario por WS
│
├── services/
│   └── workflow/
│       ├── handler_result.py ← NUEVO: HandlerResult dataclass tipado
│       ├── workflow_context.py
│       ├── workflow_engine.py
│       └── handlers/
│           ├── base.py       ← handle() retorna HandlerResult (firma actualizada)
│           └── ...
│
└── routers/
    ├── ws_canvas.py          ← SPLIT de ws.py: canvas colaborativo + presencia
    ├── ws_tramites.py        ← SPLIT de ws.py: estado trámite (público, Flutter)
    └── ws_tareas.py          ← SPLIT de ws.py: notificaciones al funcionario
```

> **Orden de implementación recomendado:**
> 1. `handler_result.py` — mínimo cambio, máximo beneficio para testing
> 2. `core/event_bus.py` + `listeners/` — desacopla el engine antes de que crezca
> 3. `core/http_client.py` — justo antes de agregar el segundo servicio externo (MIRA)
> 4. Split de `ws.py` — al arrancar el desarrollo del canvas en Ciclo 2
