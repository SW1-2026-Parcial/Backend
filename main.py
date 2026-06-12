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

# Módulo auth
from modules.auth import auth_router, users_router, departamentos_router

# Módulo policies
from modules.policies import politicas_router, versiones_router, nodos_router
from modules.policies import ws_router as policies_ws

# Módulo engine
from modules.engine import tramites_router, tasks_router
from modules.engine import ws_tramites_router, ws_tareas_router

# Módulo documents
from modules.documents import router as documents_router

# Módulo metrics
from modules.metrics import router as metrics_router

# Módulo intelligence
from modules.intelligence.analytics import router as analytics_mod
from modules.intelligence.chat import agent_router as agent_mod
from modules.intelligence.chat import reports_router as reports_mod

# sync (utilitario transversal, se queda en routers/)
from routers import sync

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

# ── Auth ──────────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(departamentos_router.router)

# ── Policies ──────────────────────────────────────────────────────────────────
app.include_router(politicas_router.router)
app.include_router(versiones_router.router)
app.include_router(nodos_router.router)
app.include_router(policies_ws.router)

# ── Engine ────────────────────────────────────────────────────────────────────
app.include_router(tramites_router.router)
app.include_router(tasks_router.router)
app.include_router(ws_tramites_router.router)
app.include_router(ws_tareas_router.router)

# ── Documents ─────────────────────────────────────────────────────────────────
app.include_router(documents_router.router)

# ── Metrics ───────────────────────────────────────────────────────────────────
app.include_router(metrics_router.router)

# ── Intelligence ──────────────────────────────────────────────────────────────
app.include_router(analytics_mod.router)
app.include_router(reports_mod.router)
app.include_router(agent_mod.router)

# ── Sync (utilitario transversal) ─────────────────────────────────────────────
app.include_router(sync.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["sistema"])
async def health():
    return {"status": "ok", "service": "sp1-backend-py", "version": "2.0.0"}
