"""
httpx.AsyncClient singleton con connection pooling.
Se inicia en el lifespan de main.py y se cierra limpiamente al apagar.

Uso:
    from core.http_client import http_client
    response = await http_client.post(url, json=payload)
"""
import httpx

# Límites de conexión: máximo 20 conexiones en total, 5 por host
_limits = httpx.Limits(max_connections=20, max_keepalive_connections=5)

http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0, connect=10.0),
    limits=_limits,
)
