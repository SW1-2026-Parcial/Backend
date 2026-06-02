import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from config import get_settings
from models.user import User
from models.departamento import Departamento
from models.politica import Politica
from models.version_politica import VersionPolitica
from models.nodo import Nodo
from models.tramite import Tramite
from models.task import Task
from models.tramite_event import TramiteEvent
# Ciclo 2
from models.documento import Documento
from models.documento_event import DocumentoEvent

logger = logging.getLogger(__name__)


async def init_db() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await init_beanie(
        database=client.get_database(settings.mongodb_db_name),
        document_models=[
            User,
            Departamento,
            Politica,
            VersionPolitica,
            Nodo,
            Tramite,
            Task,
            TramiteEvent,
            # Ciclo 2
            Documento,
            DocumentoEvent,
        ],
    )
    logger.info("Beanie inicializado — conectado a MongoDB Atlas")
