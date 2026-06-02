"""
EventBus async in-process — pub/sub desacoplado.

El WorkflowEngine emite eventos; listeners separados reaccionan.
Añadir un listener en Ciclo 2 (MIRA, agente IA, reportes) = un decorator,
sin tocar el motor.

Uso:
    # Emitir
    await event_bus.emit("task_created", {"task_id": ..., "tramite_id": ...})

    # Suscribir
    @event_bus.on("task_created")
    async def mi_listener(payload: dict) -> None:
        ...
"""
import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str) -> Callable[[Handler], Handler]:
        """Decorator para suscribir un listener a un evento."""
        def decorator(fn: Handler) -> Handler:
            self._handlers[event].append(fn)
            logger.debug("EventBus: listener '%s' registrado en '%s'", fn.__name__, event)
            return fn
        return decorator

    async def emit(self, event: str, payload: dict) -> None:
        """Emite el evento a todos los listeners registrados (en paralelo)."""
        handlers = self._handlers.get(event, [])
        if not handlers:
            return
        results = await asyncio.gather(
            *(h(payload) for h in handlers),
            return_exceptions=True,
        )
        for h, result in zip(handlers, results):
            if isinstance(result, Exception):
                logger.error("EventBus: error en listener '%s' → evento '%s': %s",
                             h.__name__, event, result)


# Instancia global
event_bus = EventBus()
