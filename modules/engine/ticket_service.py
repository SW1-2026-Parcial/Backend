"""
Generador de tickets secuenciales TRM-YYYY-XXXX.
Usa la colección 'tramites' para contar los existentes del año actual.
"""
from datetime import datetime, timezone
from models.tramite import Tramite


async def generate_ticket() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"TRM-{year}-"
    count = await Tramite.find(
        {"ticketNumber": {"$regex": f"^{prefix}"}}
    ).count()
    return f"{prefix}{count + 1:04d}"
