"""
SP1 Backend — FastAPI
Reemplaza el backend Spring Boot conectando a la misma base de datos MongoDB Atlas.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import init_db
from core.http_client import http_client

# Routers REST
from routers import auth, users, departamentos, politicas, versiones, nodos, tramites, tasks, metricas
# Ciclo 2
from routers import documentos, reportes, mira, sync, agent

# Routers WebSocket
from routers import ws_canvas, ws_tramites, ws_tareas

# Registrar listeners del EventBus (importar el paquete basta)
import listeners  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Arranque ──────────────────────────────────────────────────────────────
    await init_db()
    logger.info("✅  Beanie inicializado — conectado a MongoDB Atlas")
    logger.info("✅  Listeners del EventBus registrados")
    logger.info("🚀  SP1 Backend listo en http://localhost:8080")
    yield
    # ── Apagado ───────────────────────────────────────────────────────────────
    await http_client.aclose()
    logger.info("🛑  HTTP client cerrado")


settings = get_settings()

app = FastAPI(
    title="SP1 Backend (FastAPI)",
    description="BPM — Business Policy Manager. Reemplaza Spring Boot, misma DB Atlas.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers REST ──────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departamentos.router)
app.include_router(politicas.router)
app.include_router(versiones.router)
app.include_router(nodos.router)
app.include_router(tramites.router)
app.include_router(tasks.router)
app.include_router(metricas.router)
# Ciclo 2
app.include_router(documentos.router)
app.include_router(reportes.router)
app.include_router(mira.router)
app.include_router(sync.router)
app.include_router(agent.router)

# ── Routers WebSocket ─────────────────────────────────────────────────────────
app.include_router(ws_canvas.router)
app.include_router(ws_tramites.router)
app.include_router(ws_tareas.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["sistema"])
async def health():
    return {"status": "ok", "service": "sp1-backend-py", "version": "2.0.0"}
