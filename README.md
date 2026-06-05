# SP1 Backend — FastAPI BPM

Backend del sistema BPM (Business Policy Manager).

**Stack:** Python 3.13 · FastAPI · Beanie ODM · MongoDB Atlas · Azure Blob Storage · OpenRouter (Gemini)

---

## Requisitos previos

- Python 3.11+
- Docker Desktop (para levantar con docker-compose o solo OnlyOffice)
- Acceso a MongoDB Atlas (URI en el `.env`)

---

## Opción A — Correr nativo (desarrollo)

### 1. Clonar y entrar al proyecto

```bash
git clone <repo-url>
cd sp1-backend-py
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env   # si existe, o editar .env directamente
```

El `.env` ya tiene los valores para el entorno de desarrollo. Las variables críticas:

| Variable                          | Descripción                                                                            |
| --------------------------------- | -------------------------------------------------------------------------------------- |
| `MONGODB_URI`                     | URI de MongoDB Atlas — ya configurada                                                  |
| `JWT_SECRET`                      | Clave para firmar tokens JWT                                                           |
| `OPENROUTER_API_KEY`              | API key de OpenRouter para el agente IA y reportes                                     |
| `OPENROUTER_MODEL`                | Modelo LLM (ver sección de modelos más abajo)                                          |
| `AZURE_STORAGE_CONNECTION_STRING` | Credenciales de Azure Blob (documentos)                                                |
| `ONLYOFFICE_URL`                  | URL del Document Server — `http://localhost:8088` si corre en Docker                   |
| `BACKEND_URL`                     | URL que OnlyOffice usa para el callback — `http://host.docker.internal:8080` en nativo |

### 4. Levantar el servidor

```bash
uvicorn main:app --port 8080 --reload
```

Disponible en: `http://localhost:8080`  
Documentación interactiva: `http://localhost:8080/docs`

### 5. Levantar OnlyOffice (solo si vas a editar documentos Word/Excel)

```bash
# Desde la raíz del monorepo (donde está el docker-compose.yml)
cd ..
docker compose up -d onlyoffice
```

---

## Opción B — Todo en Docker (demo / pruebas)

Levanta el backend + OnlyOffice en un solo comando desde la raíz del monorepo:

```bash
cd ..   # raíz del monorepo (donde está docker-compose.yml)
docker compose up -d
```

Primera vez tarda ~90 segundos mientras OnlyOffice arranca.

**Comandos útiles:**

```bash
docker compose up -d              # levantar en background
docker compose down               # bajar todo
docker compose logs -f            # ver logs en vivo
docker compose logs -f backend    # solo logs del backend
docker compose up -d --build backend   # rebuild tras cambios en código
```

---

## Usuario administrador inicial

La base de datos no viene con usuarios. Hay que crear el primer admin manualmente en MongoDB Atlas.

### Desde MongoDB Compass o Atlas UI

Conectarse a la base `swp1_db`, colección `users`, e insertar:

```json
{
  "email": "admin@sp1.com",
  "passwordHash": "$2b$12$oyh8p3YjQWATQIE/E/EL.e7B0T9H/Om9f7mGWJHp/JOKfNcxdVXeq",
  "nombre": "Administrador",
  "rol": "ADMINISTRADOR",
  "departamentoId": null,
  "activo": true,
  "creadoEn": { "$date": "2026-01-01T00:00:00Z" }
}
```

Credenciales por defecto: `admin@sp1.com` / `admin1234`

Para generar un hash de otra contraseña:

```bash
python -c "from core.security import hash_password; print(hash_password('tu_password'))"
```

---

## Modelos LLM disponibles

Cambiar `OPENROUTER_MODEL` en el `.env`:

| Modelo               | ID                                       | Costo         | Cuándo usarlo                      |
| -------------------- | ---------------------------------------- | ------------- | ---------------------------------- |
| Gemini 2.0 Flash     | `google/gemini-2.0-flash-001`            | ~$0.10/1M tok | Default estable                    |
| **Claude Haiku 3.5** | `anthropic/claude-haiku-3-5`             | ~$0.80/1M tok | **Demo / producción** — mejor JSON |
| GPT-4o mini          | `openai/gpt-4o-mini`                     | ~$0.15/1M tok | Alternativa barata                 |
| Llama 3.3 70B        | `meta-llama/llama-3.3-70b-instruct:free` | Gratis        | Pruebas sin costo                  |
| Gemini Flash Exp     | `google/gemini-2.0-flash-exp:free`       | Gratis        | Fallback gratuito                  |

Tras cambiar el modelo: reiniciar el servidor o hacer `docker compose restart backend`.

---

## Estructura del proyecto

```
sp1-backend-py/
├── main.py              # Entry point — registra todos los routers
├── config.py            # Settings con pydantic-settings (lee del .env)
├── database.py          # Inicialización de Beanie + MongoDB
│
├── core/
│   ├── security.py      # JWT, bcrypt, guards (require_admin, etc.)
│   ├── exceptions.py    # Excepciones de negocio (NotFoundException, etc.)
│   ├── websocket_manager.py  # Broadcast a topics WS
│   └── event_bus.py     # Bus de eventos interno (desacopla workflow de notificaciones)
│
├── models/              # Beanie Documents (esquema MongoDB) — compartido por todos los módulos
├── schemas/             # Pydantic schemas de request/response — compartido
│
├── modules/             # Lógica de negocio organizada por dominio
│   ├── auth/            # Login, CRUD usuarios y departamentos
│   ├── policies/        # Políticas, versiones, nodos, calles, generación IA de diagramas
│   ├── engine/          # Motor de trámites, tareas, workflow engine, WebSockets
│   ├── documents/       # Gestión documental (Azure Blob + OnlyOffice)
│   ├── metrics/         # Métricas operacionales (bottlenecks, performance)
│   └── intelligence/
│       ├── analytics/   # Análisis inteligente MIRA (heurísticas, riesgos, anomalías)
│       ├── chat/        # Agente conversacional BPM + chatbot de reportes
│       ├── diagram/     # Generación de diagramas UML con IA (absorbido de sp1-ai)
│       └── llm/         # Cliente OpenRouter compartido
│
├── listeners/           # Handlers de eventos del EventBus
├── routers/sync.py      # Sincronización offline mobile
├── seed/                # Scripts para poblar datos de prueba en MongoDB
└── tests/               # Tests de integración E2E
```

---

## Endpoints principales

| Módulo         | Prefijo                              | Descripción                                   |
| -------------- | ------------------------------------ | --------------------------------------------- |
| Auth           | `/api/auth`                          | Login, JWT                                    |
| Usuarios       | `/api/users`, `/api/departamentos`   | CRUD usuarios y departamentos                 |
| Políticas      | `/api/policies`                      | Gestión de políticas BPM                      |
| Versiones      | `/api/policies/{id}/versions`        | Versiones y diagramas                         |
| Nodos / Calles | `/api/versions/{id}/nodes`, `/lanes` | Canvas del diagrama                           |
| Trámites       | `/api/tramites`                      | Iniciar y consultar trámites                  |
| Tareas         | `/api/tasks`                         | Bandeja del funcionario                       |
| Documentos     | `/api/documentos`                    | Subir, descargar, editar documentos           |
| Métricas       | `/api/metrics`                       | Bottlenecks y performance                     |
| MIRA           | `/api/mira`                          | Dashboard de análisis inteligente             |
| Agente         | `/api/agent`                         | Chat para iniciar trámites (público, sin JWT) |
| Reportes       | `/api/reportes`                      | Chatbot + generación Excel/Word               |
| Sync           | `/api/sync`                          | Push/pull para mobile offline                 |
| WebSocket      | `/ws/canvas/{id}`                    | Colaboración en tiempo real del canvas        |
| WebSocket      | `/ws/tramites/{id}`                  | Estado del trámite en tiempo real             |
| WebSocket      | `/ws/tareas/{deptoId}`               | Notificaciones de tareas al departamento      |

Documentación completa con ejemplos: `http://localhost:8080/docs`

---

## Datos de prueba (seed)

Para poblar la base con datos de ejemplo:

```bash
cd seed/
python3 gen_seed_data.py
# Genera: nodos.json, tramites.json, tasks.json, tramite_events.json, counters.json
# Importar en MongoDB Compass: Add data → Insert document (pegar el array)
```

---

## Tests

```bash
cd tests/
pip install pytest httpx
pytest test_e2e_integration.py -v
```

Los tests requieren el servidor corriendo en `localhost:8080`.
